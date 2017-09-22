from __future__ import absolute_import
from typing import Any, List, Dict, Optional, Text

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpRequest
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.cache import patch_cache_control
from six.moves import zip_longest, zip, range

from zerver.decorator import zulip_login_required, process_client
from zerver.forms import ToSForm
from zerver.lib.realm_icon import realm_icon_url
from zerver.models import Message, UserProfile, Stream, Subscription, Huddle, \
    Recipient, Realm, UserMessage, DefaultStream, RealmEmoji, RealmDomain, \
    RealmFilter, PreregistrationUser, UserActivity, \
    UserPresence, get_recipient, name_changes_disabled, email_to_username, \
    get_realm_domains
from zerver.lib.events import do_events_register
from zerver.lib.actions import update_user_presence, do_change_tos_version, \
    do_update_pointer, realm_user_count
from zerver.lib.avatar import avatar_url
from zerver.lib.i18n import get_language_list, get_language_name, \
    get_language_list_for_templates
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.lib.streams import access_stream_by_name
from zerver.lib.utils import statsd, get_subdomain

import calendar
import datetime
import logging
import os
import re
import simplejson
import time

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
    return render(
        request,
        'zerver/accounts_accept_terms.html',
        context={'form': form,
                 'email': email,
                 'special_message_template': special_message_template},
    )

def sent_time_in_epoch_seconds(user_message):
    # type: (Optional[UserMessage]) -> Optional[float]
    if user_message is None:
        return None
    # We have USE_TZ = True, so our datetime objects are timezone-aware.
    # Return the epoch seconds in UTC.
    return calendar.timegm(user_message.message.pub_date.utctimetuple())

def home(request):
    # type: (HttpRequest) -> HttpResponse
    if settings.DEVELOPMENT and os.path.exists('var/handlebars-templates/compile.error'):
        response = render(request, 'zerver/handlebars_compilation_failed.html')
        response.status_code = 500
        return response
    if not settings.ROOT_DOMAIN_LANDING_PAGE:
        return home_real(request)

    # If settings.ROOT_DOMAIN_LANDING_PAGE, sends the user the landing
    # page, not the login form, on the root domain

    subdomain = get_subdomain(request)
    if subdomain != "":
        return home_real(request)

    return render(request, 'zerver/hello.html')

@zulip_login_required
def home_real(request):
    # type: (HttpRequest) -> HttpResponse
    # We need to modify the session object every two weeks or it will expire.
    # This line makes reloading the page a sufficient action to keep the
    # session alive.
    request.session.modified = True

    user_profile = request.user

    # If a user hasn't signed the current Terms of Service, send them there
    if settings.TERMS_OF_SERVICE is not None and settings.TOS_VERSION is not None and \
       int(settings.TOS_VERSION.split('.')[0]) > user_profile.major_tos_version():
        return accounts_accept_terms(request)

    narrow = []  # type: List[List[Text]]
    narrow_stream = None
    narrow_topic = request.GET.get("topic")
    if request.GET.get("stream"):
        try:
            narrow_stream_name = request.GET.get("stream")
            (narrow_stream, ignored_rec, ignored_sub) = access_stream_by_name(
                user_profile, narrow_stream_name)
            narrow = [["stream", narrow_stream.name]]
        except Exception:
            logging.exception("Narrow parsing")
        if narrow_stream is not None and narrow_topic is not None:
            narrow.append(["topic", narrow_topic])

    register_ret = do_events_register(user_profile, request.client,
                                      apply_markdown=True, narrow=narrow)
    user_has_messages = (register_ret['max_message_id'] != -1)

    # Reset our don't-spam-users-with-email counter since the
    # user has since logged in
    if user_profile.last_reminder is not None:
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
        try:
            latest_read = UserMessage.objects.get(user_profile=user_profile,
                                                  message__id=user_profile.pointer)
        except UserMessage.DoesNotExist:
            # Don't completely fail if your saved pointer ID is invalid
            logging.warning("%s has invalid pointer %s" % (user_profile.email, user_profile.pointer))
            latest_read = None

    # Set default language and make it persist
    default_language = register_ret['default_language']
    url_lang = '/{}'.format(request.LANGUAGE_CODE)
    if not request.path.startswith(url_lang):
        translation.activate(default_language)

    request.session[translation.LANGUAGE_SESSION_KEY] = default_language

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
        server_inline_image_preview = settings.INLINE_IMAGE_PREVIEW,
        server_inline_url_embed_preview = settings.INLINE_URL_EMBED_PREVIEW,
        password_min_length = settings.PASSWORD_MIN_LENGTH,
        password_min_quality = settings.PASSWORD_MIN_ZXCVBN_QUALITY,

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
    )

    undesired_register_ret_fields = [
        'streams',
    ]
    for field_name in set(register_ret.keys()) - set(undesired_register_ret_fields):
        page_params[field_name] = register_ret[field_name]

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
        page_params["pointer"] = initial_pointer
        page_params["have_initial_messages"] = (initial_pointer != -1)
        page_params["enable_desktop_notifications"] = False

    statsd.incr('views.home')
    show_invites = True

    # Some realms only allow admins to invite users
    if user_profile.realm.invite_by_admins_only and not user_profile.is_realm_admin:
        show_invites = False

    request._log_data['extra'] = "[%s]" % (register_ret["queue_id"],)
    response = render(request, 'zerver/index.html',
                      context={'user_profile': user_profile,
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
                               },)
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response

@zulip_login_required
def desktop_home(request):
    # type: (HttpRequest) -> HttpResponse
    return HttpResponseRedirect(reverse('zerver.views.home.home'))

def apps_view(request, _):
    # type: (HttpRequest, Text) -> HttpResponse
    if settings.ZILENCER_ENABLED:
        return render(request, 'zerver/apps.html')
    return HttpResponseRedirect('https://zulipchat.com/apps/', status=301)

def is_buggy_ua(agent):
    # type: (str) -> bool
    """Discrimiate CSS served to clients based on User Agent

    Due to QTBUG-3467, @font-face is not supported in QtWebKit.
    This may get fixed in the future, but for right now we can
    just serve the more conservative CSS to all our desktop apps.
    """
    return ("Zulip Desktop/" in agent or "ZulipDesktop/" in agent) and \
        "Mac" not in agent
