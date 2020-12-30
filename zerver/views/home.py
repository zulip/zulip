import logging
import secrets
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.cache import patch_cache_control

from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import web_public_view, zulip_login_required
from zerver.forms import ToSForm
from zerver.lib.actions import do_change_tos_version, realm_user_count
from zerver.lib.home import (
    build_page_params_for_home_page_load,
    get_billing_info,
    get_user_permission_info,
)
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.lib.streams import access_stream_by_name
from zerver.lib.subdomains import get_subdomain
from zerver.lib.users import compute_show_invites_and_add_streams
from zerver.lib.utils import statsd
from zerver.models import PreregistrationUser, Realm, Stream, UserProfile
from zerver.views.compatibility import is_outdated_desktop_app, is_unsupported_browser
from zerver.views.portico import hello_view


def need_accept_tos(user_profile: Optional[UserProfile]) -> bool:
    if user_profile is None:
        return False

    if settings.TERMS_OF_SERVICE is None:  # nocoverage
        return False

    if settings.TOS_VERSION is None:
        return False

    return int(settings.TOS_VERSION.split('.')[0]) > user_profile.major_tos_version()

@zulip_login_required
def accounts_accept_terms(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ToSForm(request.POST)
        if form.is_valid():
            do_change_tos_version(request.user, settings.TOS_VERSION)
            return redirect(home)
    else:
        form = ToSForm()

    email = request.user.delivery_email
    special_message_template = None
    if request.user.tos_version is None and settings.FIRST_TIME_TOS_TEMPLATE is not None:
        special_message_template = 'zerver/' + settings.FIRST_TIME_TOS_TEMPLATE
    return render(
        request,
        'zerver/accounts_accept_terms.html',
        context={'form': form,
                 'email': email,
                 'special_message_template': special_message_template},
    )

def detect_narrowed_window(request: HttpRequest,
                           user_profile: Optional[UserProfile]) -> Tuple[List[List[str]],
                                                                         Optional[Stream],
                                                                         Optional[str]]:
    """This function implements Zulip's support for a mini Zulip window
    that just handles messages from a single narrow"""
    if user_profile is None:
        return [], None, None

    narrow: List[List[str]] = []
    narrow_stream = None
    narrow_topic = request.GET.get("topic")

    if request.GET.get("stream"):
        try:
            # TODO: We should support stream IDs and PMs here as well.
            narrow_stream_name = request.GET.get("stream")
            (narrow_stream, ignored_sub) = access_stream_by_name(
                user_profile, narrow_stream_name)
            narrow = [["stream", narrow_stream.name]]
        except Exception:
            logging.warning("Invalid narrow requested, ignoring", extra=dict(request=request))
        if narrow_stream is not None and narrow_topic is not None:
            narrow.append(["topic", narrow_topic])
    return narrow, narrow_stream, narrow_topic

def update_last_reminder(user_profile: Optional[UserProfile]) -> None:
    """Reset our don't-spam-users-with-email counter since the
    user has since logged in
    """
    if user_profile is None:
        return

    if user_profile.last_reminder is not None:  # nocoverage
        # TODO: Look into the history of last_reminder; we may have
        # eliminated that as a useful concept for non-bot users.
        user_profile.last_reminder = None
        user_profile.save(update_fields=["last_reminder"])

def compute_navbar_logo_url(page_params: Dict[str, Any]) -> str:
    if page_params["color_scheme"] == 2 and page_params["realm_night_logo_source"] != Realm.LOGO_DEFAULT:
        navbar_logo_url = page_params["realm_night_logo_url"]
    else:
        navbar_logo_url = page_params["realm_logo_url"]
    return navbar_logo_url

def home(request: HttpRequest) -> HttpResponse:
    if not settings.ROOT_DOMAIN_LANDING_PAGE:
        return home_real(request)

    # If settings.ROOT_DOMAIN_LANDING_PAGE, sends the user the landing
    # page, not the login form, on the root domain

    subdomain = get_subdomain(request)
    if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
        return home_real(request)

    return hello_view(request)

@web_public_view
def home_real(request: HttpRequest) -> HttpResponse:
    # Before we do any real work, check if the app is banned.
    client_user_agent = request.META.get("HTTP_USER_AGENT", "")
    (insecure_desktop_app, banned_desktop_app, auto_update_broken) = is_outdated_desktop_app(
        client_user_agent)
    if banned_desktop_app:
        return render(
            request,
            'zerver/insecure_desktop_app.html',
            context={
                "auto_update_broken": auto_update_broken,
            },
        )
    (unsupported_browser, browser_name) = is_unsupported_browser(client_user_agent)
    if unsupported_browser:
        return render(
            request,
            'zerver/unsupported_browser.html',
            context={
                "browser_name": browser_name,
            },
        )

    # We need to modify the session object every two weeks or it will expire.
    # This line makes reloading the page a sufficient action to keep the
    # session alive.
    request.session.modified = True

    if request.user.is_authenticated:
        user_profile = request.user
        realm = user_profile.realm
    else:
        # user_profile=None corresponds to the logged-out "web_public" visitor case.
        user_profile = None
        realm = get_valid_realm_from_request(request)

    update_last_reminder(user_profile)

    statsd.incr('views.home')

    # If a user hasn't signed the current Terms of Service, send them there
    if need_accept_tos(user_profile):
        return accounts_accept_terms(request)

    narrow, narrow_stream, narrow_topic = detect_narrowed_window(request, user_profile)

    if user_profile is not None:
        first_in_realm = realm_user_count(user_profile.realm) == 1
        # If you are the only person in the realm and you didn't invite
        # anyone, we'll continue to encourage you to do so on the frontend.
        prompt_for_invites = (
            first_in_realm and
            not PreregistrationUser.objects.filter(referred_by=user_profile).count()
        )
        needs_tutorial = user_profile.tutorial_status == UserProfile.TUTORIAL_WAITING

    else:
        first_in_realm = False
        prompt_for_invites = False
        # The current tutorial doesn't super make sense for logged-out users.
        needs_tutorial = False

    has_mobile_devices = user_profile is not None and num_push_devices_for_user(user_profile) > 0

    queue_id, page_params = build_page_params_for_home_page_load(
        request=request,
        user_profile=user_profile,
        realm=realm,
        insecure_desktop_app=insecure_desktop_app,
        has_mobile_devices=has_mobile_devices,
        narrow=narrow,
        narrow_stream=narrow_stream,
        narrow_topic=narrow_topic,
        first_in_realm=first_in_realm,
        prompt_for_invites=prompt_for_invites,
        needs_tutorial=needs_tutorial,
    )

    show_invites, show_add_streams = compute_show_invites_and_add_streams(user_profile)

    billing_info = get_billing_info(user_profile)

    request._log_data['extra'] = "[{}]".format(queue_id)

    csp_nonce = secrets.token_hex(24)

    user_permission_info = get_user_permission_info(user_profile)

    navbar_logo_url = compute_navbar_logo_url(page_params)

    response = render(request, 'zerver/app/index.html',
                      context={'user_profile': user_profile,
                               'page_params': page_params,
                               'csp_nonce': csp_nonce,
                               'search_pills_enabled': settings.SEARCH_PILLS_ENABLED,
                               'show_invites': show_invites,
                               'show_add_streams': show_add_streams,
                               'show_billing': billing_info.show_billing,
                               'corporate_enabled': settings.CORPORATE_ENABLED,
                               'show_plans': billing_info.show_plans,
                               'is_owner': user_permission_info.is_realm_owner,
                               'is_admin': user_permission_info.is_realm_admin,
                               'is_guest': user_permission_info.is_guest,
                               'color_scheme': user_permission_info.color_scheme,
                               'navbar_logo_url': navbar_logo_url,
                               'show_webathena': user_permission_info.show_webathena,
                               'embedded': narrow_stream is not None,
                               'invite_as': PreregistrationUser.INVITE_AS,
                               'max_file_upload_size_mib': settings.MAX_FILE_UPLOAD_SIZE,
                               })
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response

@zulip_login_required
def desktop_home(request: HttpRequest) -> HttpResponse:
    return HttpResponseRedirect(reverse(home))
