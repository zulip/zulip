import logging
import secrets
from typing import List, Optional, Tuple

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.cache import patch_cache_control

from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import web_public_view, zulip_login_required, zulip_redirect_to_login
from zerver.forms import ToSForm
from zerver.lib.actions import do_change_tos_version, realm_user_count
from zerver.lib.compatibility import is_outdated_desktop_app, is_unsupported_browser
from zerver.lib.home import build_page_params_for_home_page_load, get_user_permission_info
from zerver.lib.request import RequestNotes
from zerver.lib.streams import access_stream_by_name
from zerver.lib.subdomains import get_subdomain
from zerver.lib.utils import statsd
from zerver.models import PreregistrationUser, Realm, Stream, UserProfile
from zerver.views.auth import get_safe_redirect_to
from zerver.views.portico import hello_view


def need_accept_tos(user_profile: Optional[UserProfile]) -> bool:
    if user_profile is None:
        return False

    if settings.TERMS_OF_SERVICE is None:  # nocoverage
        return False

    if settings.TOS_VERSION is None:
        return False

    return int(settings.TOS_VERSION.split(".")[0]) > user_profile.major_tos_version()


@zulip_login_required
def accounts_accept_terms(request: HttpRequest) -> HttpResponse:
    assert request.user.is_authenticated

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
        special_message_template = "zerver/" + settings.FIRST_TIME_TOS_TEMPLATE
    return render(
        request,
        "zerver/accounts_accept_terms.html",
        context={
            "form": form,
            "email": email,
            "special_message_template": special_message_template,
        },
    )


def detect_narrowed_window(
    request: HttpRequest, user_profile: Optional[UserProfile]
) -> Tuple[List[List[str]], Optional[Stream], Optional[str]]:
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
            (narrow_stream, ignored_sub) = access_stream_by_name(user_profile, narrow_stream_name)
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
        client_user_agent
    )
    if banned_desktop_app:
        return render(
            request,
            "zerver/insecure_desktop_app.html",
            context={
                "auto_update_broken": auto_update_broken,
            },
        )
    (unsupported_browser, browser_name) = is_unsupported_browser(client_user_agent)
    if unsupported_browser:
        return render(
            request,
            "zerver/unsupported_browser.html",
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

        # User is logged in and hence no longer `prefers_web_public_view`.
        if "prefers_web_public_view" in request.session.keys():
            del request.session["prefers_web_public_view"]
    else:
        realm = get_valid_realm_from_request(request)

        # TODO: Ideally, we'd open Zulip directly as a spectator if
        # the URL had clicked a link to content on a web-public
        # stream.  We could maybe do this by parsing `next`, but it's
        # not super convenient with Zulip's hash-based URL scheme.

        # The "Access without an account" button on the login page
        # submits a POST to this page with this hidden field set.
        if request.POST.get("prefers_web_public_view") == "true":
            request.session["prefers_web_public_view"] = True
            # We serve a redirect here, rather than serving a page, to
            # avoid browser "Confirm form resubmission" prompts on reload.
            redirect_to = get_safe_redirect_to(request.POST.get("next"), realm.uri)
            return redirect(redirect_to)

        prefers_web_public_view = request.session.get("prefers_web_public_view")
        if not prefers_web_public_view:
            # For users who haven't opted into the spectator
            # experience, we redirect to the login page.
            return zulip_redirect_to_login(request, settings.HOME_NOT_LOGGED_IN)

        # For users who have selected public access, we load the
        # spectator experience.  We fall through to the shared code
        # for loading the application, with user_profile=None encoding
        # that we're a spectator, not a logged-in user.
        user_profile = None

    update_last_reminder(user_profile)

    statsd.incr("views.home")

    # If a user hasn't signed the current Terms of Service, send them there
    if need_accept_tos(user_profile):
        return accounts_accept_terms(request)

    narrow, narrow_stream, narrow_topic = detect_narrowed_window(request, user_profile)

    if user_profile is not None:
        first_in_realm = realm_user_count(user_profile.realm) == 1
        # If you are the only person in the realm and you didn't invite
        # anyone, we'll continue to encourage you to do so on the frontend.
        prompt_for_invites = (
            first_in_realm
            and not PreregistrationUser.objects.filter(referred_by=user_profile).count()
        )
        needs_tutorial = user_profile.tutorial_status == UserProfile.TUTORIAL_WAITING

    else:
        first_in_realm = False
        prompt_for_invites = False
        # The current tutorial doesn't super make sense for logged-out users.
        needs_tutorial = False

    queue_id, page_params = build_page_params_for_home_page_load(
        request=request,
        user_profile=user_profile,
        realm=realm,
        insecure_desktop_app=insecure_desktop_app,
        narrow=narrow,
        narrow_stream=narrow_stream,
        narrow_topic=narrow_topic,
        first_in_realm=first_in_realm,
        prompt_for_invites=prompt_for_invites,
        needs_tutorial=needs_tutorial,
    )

    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{queue_id}]"

    csp_nonce = secrets.token_hex(24)

    user_permission_info = get_user_permission_info(user_profile)

    response = render(
        request,
        "zerver/app/index.html",
        context={
            "user_profile": user_profile,
            "page_params": page_params,
            "csp_nonce": csp_nonce,
            "color_scheme": user_permission_info.color_scheme,
        },
    )
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response


@zulip_login_required
def desktop_home(request: HttpRequest) -> HttpResponse:
    return redirect(home)
