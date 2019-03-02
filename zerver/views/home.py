from typing import Any, List, Dict, Optional

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpRequest
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.cache import patch_cache_control

from zerver.context_processors import get_realm_from_request
from zerver.decorator import zulip_login_required, \
    redirect_to_login
from zerver.forms import ToSForm
from zerver.models import Message, UserProfile, \
    Realm, UserMessage, \
    PreregistrationUser, \
    get_stream_recipient, \
    get_usermessage_by_message_id
from zerver.lib.events import do_events_register
from zerver.lib.actions import do_change_tos_version, \
    realm_user_count
from zerver.lib.avatar import avatar_url
from zerver.lib.i18n import get_language_list, get_language_name, \
    get_language_list_for_templates, get_language_translation_data
from zerver.lib.json_encoder_for_html import JSONEncoderForHTML
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.lib.streams import access_stream_by_name
from zerver.lib.subdomains import get_subdomain
from zerver.lib.utils import statsd, generate_random_token
from two_factor.utils import default_device

import calendar
import logging
import os
import time

@zulip_login_required
def accounts_accept_terms(request: HttpRequest) -> HttpResponse:
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
    return render(
        request,
        'zerver/accounts_accept_terms.html',
        context={'form': form,
                 'email': email,
                 'special_message_template': special_message_template},
    )

def sent_time_in_epoch_seconds(user_message: Optional[UserMessage]) -> Optional[float]:
    if user_message is None:
        return None
    # We have USE_TZ = True, so our datetime objects are timezone-aware.
    # Return the epoch seconds in UTC.
    return calendar.timegm(user_message.message.pub_date.utctimetuple())

def get_bot_types(user_profile: UserProfile) -> List[Dict[str, object]]:
    bot_types = []
    for type_id, name in UserProfile.BOT_TYPES.items():
        bot_types.append({
            'type_id': type_id,
            'name': name,
            'allowed': type_id in user_profile.allowed_bot_types
        })
    return bot_types

def compute_navbar_logo_url(page_params: Dict[str, Any]) -> str:
    if page_params["night_mode"] and page_params["realm_night_logo_source"] != Realm.LOGO_DEFAULT:
        navbar_logo_url = page_params["realm_night_logo_url"]
    else:
        navbar_logo_url = page_params["realm_logo_url"]
    return navbar_logo_url

def home(request: HttpRequest) -> HttpResponse:
    if (settings.DEVELOPMENT and not settings.TEST_SUITE and
            os.path.exists('var/handlebars-templates/compile.error')):
        response = render(request, 'zerver/handlebars_compilation_failed.html')
        response.status_code = 500
        return response
    if not settings.ROOT_DOMAIN_LANDING_PAGE:
        return home_real(request)

    # If settings.ROOT_DOMAIN_LANDING_PAGE, sends the user the landing
    # page, not the login form, on the root domain

    subdomain = get_subdomain(request)
    if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
        return home_real(request)

    return render(request, 'zerver/hello.html')

@zulip_login_required
def home_real(request: HttpRequest) -> HttpResponse:
    # We need to modify the session object every two weeks or it will expire.
    # This line makes reloading the page a sufficient action to keep the
    # session alive.
    request.session.modified = True

    user_profile = request.user

    # If a user hasn't signed the current Terms of Service, send them there
    if settings.TERMS_OF_SERVICE is not None and settings.TOS_VERSION is not None and \
       int(settings.TOS_VERSION.split('.')[0]) > user_profile.major_tos_version():
        return accounts_accept_terms(request)

    narrow = []  # type: List[List[str]]
    narrow_stream = None
    narrow_topic = request.GET.get("topic")
    if request.GET.get("stream"):
        try:
            narrow_stream_name = request.GET.get("stream")
            (narrow_stream, ignored_rec, ignored_sub) = access_stream_by_name(
                user_profile, narrow_stream_name)
            narrow = [["stream", narrow_stream.name]]
        except Exception:
            logging.exception("Narrow parsing exception", extra=dict(request=request))
        if narrow_stream is not None and narrow_topic is not None:
            narrow.append(["topic", narrow_topic])

    register_ret = do_events_register(user_profile, request.client,
                                      apply_markdown=True, client_gravatar=True,
                                      narrow=narrow)
    user_has_messages = (register_ret['max_message_id'] != -1)

    # Reset our don't-spam-users-with-email counter since the
    # user has since logged in
    if user_profile.last_reminder is not None:  # nocoverage
        # TODO: Look into the history of last_reminder; we may have
        # eliminated that as a useful concept for non-bot users.
        user_profile.last_reminder = None
        user_profile.save(update_fields=["last_reminder"])

    # Brand new users get narrowed to PM with welcome-bot
    needs_tutorial = user_profile.tutorial_status == UserProfile.TUTORIAL_WAITING

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
        latest_read = get_usermessage_by_message_id(user_profile, user_profile.pointer)
        if latest_read is None:
            # Don't completely fail if your saved pointer ID is invalid
            logging.warning("%s has invalid pointer %s" % (user_profile.email, user_profile.pointer))

    # We pick a language for the user as follows:
    # * First priority is the language in the URL, for debugging.
    # * If not in the URL, we use the language from the user's settings.
    request_language = translation.get_language_from_path(request.path_info)
    if request_language is None:
        request_language = register_ret['default_language']
    translation.activate(request_language)
    # We also save the language to the user's session, so that
    # something reasonable will happen in logged-in portico pages.
    request.session[translation.LANGUAGE_SESSION_KEY] = translation.get_language()

    two_fa_enabled = settings.TWO_FACTOR_AUTHENTICATION_ENABLED

    # Pass parameters to the client-side JavaScript code.
    # These end up in a global JavaScript Object named 'page_params'.
    page_params = dict(
        # Server settings.
        development_environment = settings.DEVELOPMENT,
        debug_mode            = settings.DEBUG,
        test_suite            = settings.TEST_SUITE,
        poll_timeout          = settings.POLL_TIMEOUT,
        login_page            = settings.HOME_NOT_LOGGED_IN,
        root_domain_uri       = settings.ROOT_DOMAIN_URI,
        maxfilesize           = settings.MAX_FILE_UPLOAD_SIZE,
        max_avatar_file_size  = settings.MAX_AVATAR_FILE_SIZE,
        server_generation     = settings.SERVER_GENERATION,
        use_websockets        = settings.USE_WEBSOCKETS,
        save_stacktraces      = settings.SAVE_FRONTEND_STACKTRACES,
        warn_no_email         = settings.WARN_NO_EMAIL,
        server_inline_image_preview = settings.INLINE_IMAGE_PREVIEW,
        server_inline_url_embed_preview = settings.INLINE_URL_EMBED_PREVIEW,
        password_min_length = settings.PASSWORD_MIN_LENGTH,
        password_min_guesses  = settings.PASSWORD_MIN_GUESSES,
        jitsi_server_url      = settings.JITSI_SERVER_URL,
        search_pills_enabled  = settings.SEARCH_PILLS_ENABLED,

        # Misc. extra data.
        have_initial_messages = user_has_messages,
        initial_servertime    = time.time(),  # Used for calculating relative presence age
        default_language_name = get_language_name(register_ret['default_language']),
        language_list_dbl_col = get_language_list_for_templates(register_ret['default_language']),
        language_list         = get_language_list(),
        needs_tutorial        = needs_tutorial,
        first_in_realm        = first_in_realm,
        prompt_for_invites    = prompt_for_invites,
        furthest_read_time    = sent_time_in_epoch_seconds(latest_read),
        has_mobile_devices    = num_push_devices_for_user(user_profile) > 0,
        bot_types             = get_bot_types(user_profile),
        two_fa_enabled        = two_fa_enabled,
        # Adding two_fa_enabled as condition saves us 3 queries when
        # 2FA is not enabled.
        two_fa_enabled_user   = two_fa_enabled and bool(default_device(user_profile)),
    )

    undesired_register_ret_fields = [
        'streams',
    ]
    for field_name in set(register_ret.keys()) - set(undesired_register_ret_fields):
        page_params[field_name] = register_ret[field_name]

    if narrow_stream is not None:
        # In narrow_stream context, initial pointer is just latest message
        recipient = get_stream_recipient(narrow_stream.id)
        try:
            initial_pointer = Message.objects.filter(recipient=recipient).order_by('id').reverse()[0].id
        except IndexError:
            initial_pointer = -1
        page_params["narrow_stream"] = narrow_stream.name
        if narrow_topic is not None:
            page_params["narrow_topic"] = narrow_topic
        page_params["narrow"] = [dict(operator=term[0], operand=term[1]) for term in narrow]
        page_params["max_message_id"] = initial_pointer
        page_params["pointer"] = initial_pointer
        page_params["have_initial_messages"] = (initial_pointer != -1)
        page_params["enable_desktop_notifications"] = False

    statsd.incr('views.home')
    show_invites = True

    # Some realms only allow admins to invite users
    if user_profile.realm.invite_by_admins_only and not user_profile.is_realm_admin:
        show_invites = False
    if user_profile.is_guest:
        show_invites = False

    show_billing = False
    show_plans = False
    if settings.CORPORATE_ENABLED:
        from corporate.models import Customer, CustomerPlan
        if user_profile.is_billing_admin or user_profile.is_realm_admin:
            customer = Customer.objects.filter(realm=user_profile.realm).first()
            if customer is not None and CustomerPlan.objects.filter(customer=customer).exists():
                show_billing = True
        if user_profile.realm.plan_type == Realm.LIMITED:
            show_plans = True

    request._log_data['extra'] = "[%s]" % (register_ret["queue_id"],)

    page_params['translation_data'] = {}
    if request_language != 'en':
        page_params['translation_data'] = get_language_translation_data(request_language)

    csp_nonce = generate_random_token(48)
    emojiset = user_profile.emojiset
    if emojiset == UserProfile.TEXT_EMOJISET:
        # If current emojiset is `TEXT_EMOJISET`, then fallback to
        # GOOGLE_EMOJISET for picking which spritesheet's CSS to
        # include (and thus how to display emojis in the emoji picker
        # and composebox typeahead).
        emojiset = UserProfile.GOOGLE_BLOB_EMOJISET

    navbar_logo_url = compute_navbar_logo_url(page_params)

    response = render(request, 'zerver/app/index.html',
                      context={'user_profile': user_profile,
                               'emojiset': emojiset,
                               'page_params': JSONEncoderForHTML().encode(page_params),
                               'csp_nonce': csp_nonce,
                               'avatar_url': avatar_url(user_profile),
                               'show_debug':
                               settings.DEBUG and ('show_debug' in request.GET),
                               'pipeline': settings.PIPELINE_ENABLED,
                               'search_pills_enabled': settings.SEARCH_PILLS_ENABLED,
                               'show_invites': show_invites,
                               'show_billing': show_billing,
                               'show_plans': show_plans,
                               'is_admin': user_profile.is_realm_admin,
                               'is_guest': user_profile.is_guest,
                               'night_mode': user_profile.night_mode,
                               'navbar_logo_url': navbar_logo_url,
                               'show_webathena': user_profile.realm.webathena_enabled,
                               'enable_feedback': settings.ENABLE_FEEDBACK,
                               'embedded': narrow_stream is not None,
                               'invite_as': PreregistrationUser.INVITE_AS,
                               },)
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response

@zulip_login_required
def desktop_home(request: HttpRequest) -> HttpResponse:
    return HttpResponseRedirect(reverse('zerver.views.home.home'))

def apps_view(request: HttpRequest, _: str) -> HttpResponse:
    if settings.ZILENCER_ENABLED:
        return render(request, 'zerver/apps.html')
    return HttpResponseRedirect('https://zulipchat.com/apps/', status=301)

def plans_view(request: HttpRequest) -> HttpResponse:
    realm = get_realm_from_request(request)
    if realm is not None:
        if realm.plan_type == Realm.SELF_HOSTED:
            return HttpResponseRedirect('https://zulipchat.com/plans')
        if not request.user.is_authenticated():
            return redirect_to_login(next="plans")
    return render(request, "zerver/plans.html")
