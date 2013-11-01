from __future__ import absolute_import

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext, loader
from django.utils.timezone import now, utc
from django.utils.html import mark_safe
from django.utils.cache import patch_cache_control
from django.core.exceptions import ValidationError
from django.core import validators
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.db.models import Q, F
from django.core.mail import send_mail, mail_admins, EmailMessage
from django.db import transaction, IntegrityError
from zerver.models import Message, UserProfile, Stream, Subscription, \
    Recipient, Realm, UserMessage, bulk_get_recipients, \
    PreregistrationUser, get_client, MitUser, UserActivity, UserActivityInterval, \
    MAX_SUBJECT_LENGTH, get_stream, bulk_get_streams, UserPresence, \
    get_recipient, valid_stream_name, to_dict_cache_key, to_dict_cache_key_id, \
    extract_message_dict, stringify_message_dict, parse_usermessage_flags, \
    email_to_domain, email_to_username, get_realm, completely_open, \
    is_super_user, AppleDeviceToken, get_active_user_dicts_in_realm
from zerver.lib.actions import do_remove_subscription, bulk_remove_subscriptions, \
    do_change_password, create_mirror_user_if_needed, compute_irc_user_fullname, \
    compute_jabber_user_fullname, do_change_full_name, \
    do_change_enable_desktop_notifications, do_change_enter_sends, do_change_enable_sounds, \
    do_send_confirmation_email, do_activate_user, do_create_user, check_send_message, \
    do_change_subscription_property, internal_send_message, \
    create_stream_if_needed, gather_subscriptions, subscribed_to_stream, \
    update_user_presence, bulk_add_subscriptions, do_update_message_flags, \
    recipient_for_emails, extract_recipients, do_events_register, \
    get_status_dict, do_change_enable_offline_email_notifications, \
    do_update_message, internal_prep_message, \
    do_send_messages, do_add_subscription, get_default_subs, do_deactivate, \
    user_email_is_unique, do_invite_users, do_refer_friend, compute_mit_user_fullname, \
    do_add_alert_words, do_remove_alert_words, do_set_alert_words, get_subscriber_emails, \
    update_user_activity_interval, do_set_muted_topics, do_rename_stream, \
    notify_for_streams_by_default, do_change_enable_offline_push_notifications
from zerver.lib.create_user import random_api_key
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.forms import RegistrationForm, HomepageForm, ToSForm, CreateBotForm, \
    is_inactive, not_mit_mailing_list
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django_openid_auth.views import default_render_failure, login_complete
from openid.consumer.consumer import SUCCESS as openid_SUCCESS
from openid.extensions import ax
from zerver.lib import bugdown
from zerver.lib.alert_words import user_alert_words

from zerver.decorator import require_post, \
    authenticated_api_view, authenticated_json_post_view, \
    has_request_variables, authenticated_json_view, \
    to_non_negative_int, json_to_dict, json_to_list, json_to_bool, \
    JsonableError, get_user_profile_by_email, \
    authenticated_rest_api_view, process_as_post, REQ, rate_limit_user, \
    zulip_internal
from zerver.lib.query import last_n
from zerver.lib.avatar import avatar_url
from zerver.lib.upload import upload_message_image_through_web_client, upload_avatar_image, \
    get_signed_upload_url
from zerver.lib.response import json_success, json_error, json_response, json_method_not_allowed
from zerver.lib.cache import cache_get_many, cache_set_many, \
    generic_bulk_cached_fetch
from zerver.lib.unminify import SourceMap
from zerver.lib.queue import queue_json_publish
from zerver.lib.utils import statsd, generate_random_token
from zerver.lib.timestamp import timestamp_to_datetime
from zerver import tornado_callbacks
from django.db import connection

from confirmation.models import Confirmation

import subprocess
import calendar
import datetime
import itertools
import ujson
import simplejson
import re
import urllib
import base64
import time
import logging
import os
from collections import defaultdict

from zerver.lib.rest import rest_dispatch as _rest_dispatch
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

def send_signup_message(sender, signups_stream, user_profile,
                        internal=False, realm=None):
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    # Send notification to realm notifications stream if it exists
    # Don't send notification for the first user in a realm
    user_dicts = get_active_user_dicts_in_realm(user_profile.realm)
    realm_user_count = len([user_dict for user_dict in user_dicts if not user_dict["is_bot"]])
    if user_profile.realm.notifications_stream is not None and realm_user_count > 1:
        internal_send_message(sender, "stream",
                              user_profile.realm.notifications_stream.name,
                              "New users", "%s just signed up for Zulip. Say hello!" % \
                                (user_profile.full_name,),
                              realm=user_profile.realm)

    internal_send_message(sender,
            "stream", signups_stream, user_profile.realm.domain,
            "%s <`%s`> just signed up for Zulip!%s(total: **%i**)" % (
                user_profile.full_name,
                user_profile.email,
                internal_blurb,
                realm_user_count,
                )
            )

def notify_new_user(user_profile, internal=False):
    send_signup_message("new-user-bot@zulip.com", "signups", user_profile, internal)
    statsd.gauge("users.signups.%s" % (user_profile.realm.domain.replace('.', '_')), 1, delta=True)

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

@require_post
@has_request_variables
def beta_signup_submission(request, name=REQ, email=REQ,
                           company=REQ, count=REQ, product=REQ):
    content = """Name: %s
Email: %s
Company: %s
# users: %s
Currently using: %s""" % (name, email, company, count, product,)
    subject = "Interest in Zulip: %s" % (company,)
    from_email = '"%s" <zulip+signups@zulip.com>' % (name,)
    to_email = '"Zulip Signups" <zulip+signups@zulip.com>'
    headers = {'Reply-To' : '"%s" <%s>' % (name, email,)}
    msg = EmailMessage(subject, content, from_email, [to_email], headers=headers)
    msg.send()
    return json_success()

@require_post
def accounts_register(request):
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    mit_beta_user = isinstance(confirmation.content_object, MitUser)

    validators.validate_email(email)
    # If someone invited you, you are joining their realm regardless
    # of your e-mail address.
    #
    # MitUsers can't be referred and don't have a referred_by field.
    if not mit_beta_user and prereg_user.referred_by:
        domain = prereg_user.referred_by.realm.domain
    elif not mit_beta_user and prereg_user.realm:
        # You have a realm set, even though nobody referred you. This
        # happens if you sign up through a special URL for an open
        # realm.
        domain = prereg_user.realm.domain
    else:
        domain = email_to_domain(email)

    try:
        if mit_beta_user:
            # MIT users already exist, but are supposed to be inactive.
            is_inactive(email)
        else:
            # Other users should not already exist at all.
            user_email_is_unique(email)
    except ValidationError:
        return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + urllib.quote_plus(email))

    if request.POST.get('from_confirmation'):
        if domain == "mit.edu":
            hesiod_name = compute_mit_user_fullname(email)
            form = RegistrationForm(
                    initial={'full_name': hesiod_name if "@" not in hesiod_name else ""})
        else:
            form = RegistrationForm()
    else:
        form = RegistrationForm(request.POST)
        if form.is_valid():
            password   = form.cleaned_data['password']
            full_name  = form.cleaned_data['full_name']
            short_name = email_to_username(email)
            (realm, _) = Realm.objects.get_or_create(domain=domain)
            first_in_realm = len(UserProfile.objects.filter(realm=realm)) == 0

            # FIXME: sanitize email addresses and fullname
            if mit_beta_user:
                try:
                    user_profile = get_user_profile_by_email(email)
                except UserProfile.DoesNotExist:
                    user_profile = do_create_user(email, password, realm, full_name, short_name)
                do_activate_user(user_profile)
                do_change_password(user_profile, password)
                do_change_full_name(user_profile, full_name)
            else:
                user_profile = do_create_user(email, password, realm, full_name, short_name)
                # We want to add the default subs list iff there were no subs
                # specified when the user was invited.
                streams = prereg_user.streams.all()
                if len(streams) == 0:
                    streams = get_default_subs(user_profile)
                bulk_add_subscriptions(streams, [user_profile])

                # Give you the last 100 messages on your streams, so you have
                # something to look at in your home view once you finish the
                # tutorial.
                one_week_ago = now() - datetime.timedelta(weeks=1)
                recipients = Recipient.objects.filter(type=Recipient.STREAM,
                                                      type_id__in=[stream.id for stream in streams])
                messages = Message.objects.filter(recipient_id__in=recipients, pub_date__gt=one_week_ago).order_by("-id")[0:100]
                if len(messages) > 0:
                    ums_to_create = [UserMessage(user_profile=user_profile, message=message,
                                                 flags=UserMessage.flags.read)
                                     for message in messages]

                    UserMessage.objects.bulk_create(ums_to_create)

                if prereg_user.referred_by is not None:
                    # This is a cross-realm private message.
                    internal_send_message("new-user-bot@zulip.com",
                            "private", prereg_user.referred_by.email, user_profile.realm.domain,
                            "%s <`%s`> accepted your invitation to join Zulip!" % (
                                user_profile.full_name,
                                user_profile.email,
                                )
                            )
            # Mark any other PreregistrationUsers that are STATUS_ACTIVE as inactive
            # so we can find the PreregistrationUser that we are actually working
            # with here
            PreregistrationUser.objects.filter(email=email)             \
                                       .exclude(id=prereg_user.id)      \
                                       .update(status=0)

            notify_new_user(user_profile)
            queue_json_publish(
                    "signups",
                    {
                        'EMAIL': email,
                        'merge_vars': {
                            'NAME': full_name,
                            'REALM': domain,
                            'OPTIN_IP': request.META['REMOTE_ADDR'],
                            'OPTIN_TIME': datetime.datetime.isoformat(datetime.datetime.now()),
                        },
                    },
                    lambda event: None)

            login(request, authenticate(username=email, password=password))

            if first_in_realm:
                return HttpResponseRedirect(reverse('zerver.views.initial_invite_page'))
            else:
                return HttpResponseRedirect(reverse('zerver.views.home'))

    return render_to_response('zerver/register.html',
            {'form': form,
             'company_name': domain,
             'email': email,
             'key': key,
             'gafyd_name': request.POST.get('gafyd_name', False),
            },
        context_instance=RequestContext(request))

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def accounts_accept_terms(request):
    email = request.user.email
    domain = email_to_domain(email)
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

def handle_openid_errors(request, issue, openid_response=None):
    if issue == "Unknown user":
        if openid_response is not None and openid_response.status == openid_SUCCESS:
            ax_response = ax.FetchResponse.fromSuccessResponse(openid_response)
            google_email = openid_response.getSigned('http://openid.net/srv/ax/1.0', 'value.email')
            full_name = " ".join((
                    ax_response.get('http://axschema.org/namePerson/first')[0],
                    ax_response.get('http://axschema.org/namePerson/last')[0]))
            form = create_homepage_form(request, user_info={'email': google_email})
            request.verified_email = None
            if form.is_valid():
                # Construct a PreregistrationUser object and send the user over to
                # the confirmation view.
                prereg_user = create_preregistration_user(google_email, request)
                return redirect("".join((
                    "/",
                    # Split this so we only get the part after the /
                    Confirmation.objects.get_link_for_object(prereg_user).split("/", 3)[3],
                    '?gafyd_name=',
                    # urllib does not handle Unicode, so coerece to encoded byte string
                    # Explanation: http://stackoverflow.com/a/5605354/90777
                    urllib.quote_plus(full_name.encode('utf8')))))
            else:
                return render_to_response('zerver/accounts_home.html', {'form': form})
    return default_render_failure(request, issue)

def process_openid_login(request):
    return login_complete(request, render_failure=handle_openid_errors)

def login_page(request, **kwargs):
    template_response = django_login_page(request, **kwargs)
    try:
        template_response.context_data['email'] = request.GET['email']
    except KeyError:
        pass
    return template_response

@authenticated_json_post_view
@has_request_variables
def json_bulk_invite_users(request, user_profile, invitee_emails=REQ(converter=json_to_list)):
    invitee_emails = set(invitee_emails)
    streams = get_default_subs(user_profile)

    ret_error, error_data = do_invite_users(user_profile, invitee_emails, streams)

    if ret_error is not None:
        return json_error(data=error_data, msg=ret_error)
    else:
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
    if not completely_open(domain):
        domain = None
    # MIT users who are not explicitly signing up for an open realm
    # require special handling (They may already have an (inactive)
    # account, for example)
    if email_to_domain(email) == "mit.edu" and not domain:
        prereg_user, created = MitUser.objects.get_or_create(email=email)
    else:
        prereg_user = PreregistrationUser(email=email, realm=get_realm(domain))
        prereg_user.save()

    request.session["domain"] = None

    return prereg_user

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

def accounts_home(request):
    if request.method == 'POST':
        form = create_homepage_form(request, user_info=request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            prereg_user = create_preregistration_user(email, request)
            Confirmation.objects.send_confirmation(prereg_user, email)
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

    # Don't include messages that aren't in your home view, as they might never
    # be read.
    return UserMessage.objects.filter(
        user_profile=user_profile, message_id__gt=user_profile.pointer).exclude(
        message__recipient__type=Recipient.STREAM,
        message__recipient__id__in=not_in_home_view_recipients).count()

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

    register_ret = do_events_register(user_profile, request.client,
                                      apply_markdown=True)
    user_has_messages = (register_ret['max_message_id'] != -1)

    # Reset our don't-spam-users-with-email counter since the
    # user has since logged in
    if not user_profile.last_reminder is None:
        user_profile.last_reminder = None
        user_profile.save(update_fields=["last_reminder"])

    # Brand new users get the tutorial
    needs_tutorial = settings.TUTORIAL_ENABLED and \
        user_profile.tutorial_status != UserProfile.TUTORIAL_FINISHED

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

    # Pass parameters to the client-side JavaScript code.
    # These end up in a global JavaScript Object named 'page_params'.
    page_params = simplejson.encoder.JSONEncoderForHTML().encode(dict(
        local_server          = settings.LOCAL_SERVER,
        debug_mode            = settings.DEBUG,
        test_suite            = settings.TEST_SUITE,
        poll_timeout          = settings.POLL_TIMEOUT,
        have_initial_messages = user_has_messages,
        stream_list           = register_ret['subscriptions'],
        unsubbed_info         = register_ret['unsubscribed'],
        email_dict            = register_ret['email_dict'],
        people_list           = register_ret['realm_users'],
        initial_pointer       = register_ret['pointer'],
        initial_presences     = register_ret['presences'],
        initial_servertime    = time.time(), # Used for calculating relative presence age
        fullname              = user_profile.full_name,
        email                 = user_profile.email,
        domain                = user_profile.realm.domain,
        realm_name            = user_profile.realm.name,
        enter_sends           = user_profile.enter_sends,
        referrals             = register_ret['referrals'],
        realm_emoji           = register_ret['realm_emoji'],
        needs_tutorial        = needs_tutorial,
        desktop_notifications_enabled =
            user_profile.enable_desktop_notifications,
        sounds_enabled =
            user_profile.enable_sounds,
        enable_offline_email_notifications =
            user_profile.enable_offline_email_notifications,
        enable_offline_push_notifications =
            user_profile.enable_offline_push_notifications,
        event_queue_id        = register_ret['queue_id'],
        last_event_id         = register_ret['last_event_id'],
        max_message_id        = register_ret['max_message_id'],
        unread_count          = approximate_unread_count(user_profile),
        furthest_read_time    = sent_time_in_epoch_seconds(latest_read),
        staging               = settings.STAGING_DEPLOYED or not settings.DEPLOYED,
        alert_words           = register_ret['alert_words'],
        muted_topics          = register_ret['muted_topics'],
        show_admin            = user_profile.show_admin,
        notify_for_streams_by_default = notify_for_streams_by_default(user_profile),
        has_mobile_devices    = num_push_devices_for_user(user_profile) > 0
    ))

    statsd.incr('views.home')
    show_invites = True

    # For the CUSTOMER4 student realm, only let instructors (who have
    # @customer4.invalid addresses) invite new users.
    if ((user_profile.realm.domain == "users.customer4.invalid") and
        (not user_profile.email.lower().endswith("@customer4.invalid"))):
        show_invites = False

    response = render_to_response('zerver/index.html',
                                  {'user_profile': user_profile,
                                   'page_params' : page_params,
                                   'avatar_url': avatar_url(user_profile),
                                   'nofontface': is_buggy_ua(request.META["HTTP_USER_AGENT"]),
                                   'show_debug':
                                       settings.DEBUG and ('show_debug' in request.GET),
                                   'show_invites': show_invites,
                                   'show_admin': user_profile.show_admin,
                                   'show_webathena': user_profile.realm.domain == "mit.edu",
                                   },
                                  context_instance=RequestContext(request))
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response

def is_buggy_ua(agent):
    """Discrimiate CSS served to clients based on User Agent

    Due to QTBUG-3467, @font-face is not supported in QtWebKit.
    This may get fixed in the future, but for right now we can
    just serve the more conservative CSS to all our desktop apps.
    """
    return ("Humbug Desktop/" in agent or "Zulip Desktop/" in agent) and \
        not "Macintosh" in agent

def get_pointer_backend(request, user_profile):
    return json_success({'pointer': user_profile.pointer})

@authenticated_api_view
def api_update_pointer(request, user_profile):
    return update_pointer_backend(request, user_profile)

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

    prev_pointer = user_profile.pointer
    user_profile.pointer = pointer
    user_profile.save(update_fields=["pointer"])

    if request.client.name.lower() in ['android', 'iphone']:
        # TODO (leo)
        # Until we handle the new read counts in the mobile apps natively,
        # this is a shim that will mark as read any messages up until the
        # pointer move
        UserMessage.objects.filter(user_profile=user_profile,
                                   message__id__gt=prev_pointer,
                                   message__id__lte=pointer,
                                   flags=~UserMessage.flags.read)        \
                           .update(flags=F('flags').bitor(UserMessage.flags.read))

    if settings.TORNADO_SERVER:
        tornado_callbacks.send_notification(dict(
            type            = 'pointer_update',
            user            = user_profile.id,
            new_pointer     = pointer))

    return json_success()

@authenticated_json_post_view
def json_get_old_messages(request, user_profile):
    return get_old_messages_backend(request, user_profile)

@authenticated_api_view
@has_request_variables
def api_get_old_messages(request, user_profile,
                         apply_markdown=REQ(default=False,
                                            converter=ujson.loads)):
    return get_old_messages_backend(request, user_profile,
                                    apply_markdown=apply_markdown)

class BadNarrowOperator(Exception):
    def __init__(self, desc):
        self.desc = desc

    def to_json_error_msg(self):
        return 'Invalid narrow operator: ' + self.desc

class NarrowBuilder(object):
    def __init__(self, user_profile, prefix):
        self.user_profile = user_profile
        self.prefix = prefix

    def __call__(self, query, operator, operand):
        # We have to be careful here because we're letting users call a method
        # by name! The prefix 'by_' prevents it from colliding with builtin
        # Python __magic__ stuff.
        method_name = 'by_' + operator.replace('-', '_')
        if method_name == 'by_search':
            return self.do_search(query, operand)
        method = getattr(self, method_name, None)
        if method is None:
            raise BadNarrowOperator('unknown operator ' + operator)
        return query.filter(method(operand))

    # Wrapper for Q() which adds self.prefix to all the keys
    def pQ(self, **kwargs):
        return Q(**dict((self.prefix + key, kwargs[key]) for key in kwargs.keys()))

    def by_is(self, operand):
        if operand == 'private':
            return (self.pQ(recipient__type=Recipient.PERSONAL) |
                    self.pQ(recipient__type=Recipient.HUDDLE))
        elif operand == 'starred':
            return Q(flags=UserMessage.flags.starred)
        elif operand == 'mentioned':
            return Q(flags=UserMessage.flags.mentioned)
        elif operand == 'alerted':
            return Q(flags=UserMessage.flags.mentioned)
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    def by_stream(self, operand):
        stream = get_stream(operand, self.user_profile.realm)
        if stream is None:
            raise BadNarrowOperator('unknown stream ' + operand)

        if self.user_profile.realm.domain == "mit.edu":
            # MIT users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
            # (unsocial, ununsocial, social.d, etc)
            m = re.search(r'^(?:un)*(.+?)(?:\.d)*$', stream.name, re.IGNORECASE)
            if m:
                base_stream_name = m.group(1)
            else:
                base_stream_name = stream.name

            matching_streams = Stream.objects.filter(realm=self.user_profile.realm,
                                                     name__iregex=r'^(un)*%s(\.d)*$' % (re.escape(base_stream_name),))
            matching_stream_ids = [matching_stream.id for matching_stream in matching_streams]
            recipients = bulk_get_recipients(Recipient.STREAM, matching_stream_ids).values()
            return self.pQ(recipient__in=recipients)

        recipient = get_recipient(Recipient.STREAM, type_id=stream.id)
        return self.pQ(recipient=recipient)

    def by_topic(self, operand):
        if self.user_profile.realm.domain == "mit.edu":
            # MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
            # (foo, foo.d, foo.d.d, etc)
            m = re.search(r'^(.*?)(?:\.d)*$', operand, re.IGNORECASE)
            if m:
                base_topic = m.group(1)
            else:
                base_topic = operand

            # Additionally, MIT users expect the empty instance and
            # instance "personal" to be the same.
            if base_topic in ('', 'personal', '(instance "")'):
                regex = r'^(|personal|\(instance ""\))(\.d)*$'
            else:
                regex = r'^%s(\.d)*$' % (re.escape(base_topic),)

            return self.pQ(subject__iregex=regex)

        return self.pQ(subject__iexact=operand)

    def by_sender(self, operand):
        try:
            sender = get_user_profile_by_email(operand)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator('unknown user ' + operand)

        return self.pQ(sender=sender)

    def by_near(self, operand):
        return Q()

    def by_id(self, operand):
        return self.pQ(id=operand)

    def by_pm_with(self, operand):
        if ',' in operand:
            # Huddle
            try:
                emails = [e.strip() for e in operand.split(',')]
                recipient = recipient_for_emails(emails, False,
                    self.user_profile, self.user_profile)
            except ValidationError:
                raise BadNarrowOperator('unknown recipient ' + operand)
            return self.pQ(recipient=recipient)
        else:
            # Personal message
            self_recipient = get_recipient(Recipient.PERSONAL, type_id=self.user_profile.id)
            if operand == self.user_profile.email:
                # Personals with self
                return self.pQ(recipient__type=Recipient.PERSONAL,
                          sender=self.user_profile, recipient=self_recipient)

            # Personals with other user; include both directions.
            try:
                narrow_profile = get_user_profile_by_email(operand)
            except UserProfile.DoesNotExist:
                raise BadNarrowOperator('unknown user ' + operand)

            narrow_recipient = get_recipient(Recipient.PERSONAL, narrow_profile.id)
            return ((self.pQ(sender=narrow_profile) & self.pQ(recipient=self_recipient)) |
                    (self.pQ(sender=self.user_profile) & self.pQ(recipient=narrow_recipient)))

    def do_search(self, query, operand):
        if "postgres" in settings.DATABASES["default"]["ENGINE"]:
            tsquery = "plainto_tsquery('zulip.english_us_search', %s)"
            where = "search_tsvector @@ " + tsquery
            match_content = "ts_headline('zulip.english_us_search', rendered_content, " \
                + tsquery + ", 'StartSel=\"<span class=\"\"highlight\"\">\", StopSel=</span>, " \
                "HighlightAll=TRUE')"
            # We HTML-escape the subject in Postgres to avoid doing a server round-trip
            match_subject = "ts_headline('zulip.english_us_search', escape_html(subject), " \
                + tsquery + ", 'StartSel=\"<span class=\"\"highlight\"\">\", StopSel=</span>, " \
                "HighlightAll=TRUE')"

            # Do quoted string matching.  We really want phrase
            # search here so we can ignore punctuation and do
            # stemming, but there isn't a standard phrase search
            # mechanism in Postgres
            for term in re.findall('"[^"]+"|\S+', operand):
                if term[0] == '"' and term[-1] == '"':
                    term = term[1:-1]
                    query = query.filter(self.pQ(content__icontains=term) |
                                         self.pQ(subject__icontains=term))

            return query.extra(select={'match_content': match_content,
                                       'match_subject': match_subject},
                               where=[where],
                               select_params=[operand, operand], params=[operand])
        else:
            for word in operand.split():
                query = query.filter(self.pQ(content__icontains=word) |
                                     self.pQ(subject__icontains=word))
            return query


def narrow_parameter(json):
    # FIXME: A hack to support old mobile clients
    if json == '{}':
        return None

    data = json_to_list(json)
    for elem in data:
        if not isinstance(elem, list):
            raise ValueError("element is not a list")
        if (len(elem) != 2
            or any(not isinstance(x, str) and not isinstance(x, unicode)
                   for x in elem)):
            raise ValueError("element is not a string pair")
    return data

def is_public_stream(request, stream, realm):
    if not valid_stream_name(stream):
        raise JsonableError("Invalid stream name")
    stream = get_stream(stream, realm)
    if stream is None:
        return False
    return stream.is_public()

@has_request_variables
def get_old_messages_backend(request, user_profile,
                             anchor = REQ(converter=int),
                             num_before = REQ(converter=to_non_negative_int),
                             num_after = REQ(converter=to_non_negative_int),
                             narrow = REQ('narrow', converter=narrow_parameter, default=None),
                             apply_markdown=REQ(default=True,
                                                converter=ujson.loads)):
    include_history = False
    if narrow is not None:
        for operator, operand in narrow:
            if operator == "stream":
                if is_public_stream(request, operand, user_profile.realm):
                    include_history = True
        # Disable historical messages if the user is narrowing to show
        # only starred messages (or anything else that's a property on
        # the UserMessage table).  There cannot be historical messages
        # in these cases anyway.
        for operator, operand in narrow:
            if operator == "is" and operand == "starred":
                include_history = False

    if include_history:
        prefix = ""
        query = Message.objects.only("id").order_by('id')
    else:
        prefix = "message__"
        # Conceptually this query should be
        #   UserMessage.objects.filter(user_profile=user_profile).order_by('message')
        #
        # However, our do_search code above requires that there be a
        # unique 'rendered_content' row in the query, so we need to
        # somehow get the 'message' table into the query without
        # actually fetching all the rows from the message table (since
        # doing so would cause Django to consume a lot of resources
        # rendering them).  The following achieves these objectives.
        query = UserMessage.objects.select_related("message").only("flags", "id", "message__id") \
            .filter(user_profile=user_profile).order_by('message')

    # Add some metadata to our logging data for narrows
    if narrow is not None:
        operator_data = ",".join(operator for (operator, operand) in narrow)
        request._extra_log_data = "[%s]" % (operator_data,)

    num_extra_messages = 1
    is_search = False

    if narrow is None:
        use_raw_query = True
    else:
        use_raw_query = False
        num_extra_messages = 0
        build = NarrowBuilder(user_profile, prefix)
        for operator, operand in narrow:
            if operator == 'search':
                is_search = True
            query = build(query, operator, operand)

    def add_prefix(**kwargs):
        return dict((prefix + key, kwargs[key]) for key in kwargs.keys())

    # We add 1 to the number of messages requested if no narrow was
    # specified to ensure that the resulting list always contains the
    # anchor message.  If a narrow was specified, the anchor message
    # might not match the narrow anyway.
    if num_after != 0:
        num_after += num_extra_messages
    else:
        num_before += num_extra_messages

    before_result = []
    after_result = []
    if num_before != 0:
        before_anchor = anchor
        if num_after != 0:
            # Don't include the anchor in both the before query and the after query
            before_anchor = anchor - 1
        if use_raw_query:
            cursor = connection.cursor()
            # These queries should always be equivalent to what we
            # would do in the !use_raw_query case.  In this case we
            # don't actually need the zerver_message join at all.
            cursor.execute("SELECT message_id, flags FROM zerver_usermessage "
                           "WHERE user_profile_id = %s and message_id <= %s " +
                           "ORDER BY message_id DESC LIMIT %s", [user_profile.id, before_anchor, num_before])
            before_result = reversed(cursor.fetchall())
        else:
            before_result = last_n(num_before, query.filter(**add_prefix(id__lte=before_anchor)))
    if num_after != 0:
        if use_raw_query:
            cursor = connection.cursor()
            # These queries should always be equivalent to what we
            # would do in the !use_raw_query case.  In this case we
            # don't actually need the zerver_message join at all.
            cursor.execute("SELECT message_id, flags FROM zerver_usermessage "
                           "WHERE user_profile_id = %s and message_id >= %s " +
                           "ORDER BY message_id LIMIT %s", [user_profile.id, anchor, num_after])
            after_result = cursor.fetchall()
        else:
            after_result = query.filter(**add_prefix(id__gte=anchor))[:num_after]
    query_result = list(before_result) + list(after_result)

    # The following is a little messy, but ensures that the code paths
    # are similar regardless of the value of include_history.  The
    # 'user_messages' dictionary maps each message to the user's
    # UserMessage object for that message, which we will attach to the
    # rendered message dict before returning it.  We attempt to
    # bulk-fetch rendered message dicts from memcached using the
    # 'messages' list.
    search_fields = dict()
    message_ids = []
    user_message_flags = {}
    if use_raw_query:
        for row in query_result:
            (message_id, flags_val) = row
            user_message_flags[message_id] = parse_usermessage_flags(flags_val)
            message_ids.append(message_id)
    elif include_history:
        user_message_flags = dict((user_message.message_id, user_message.flags_list()) for user_message in
                                  UserMessage.objects.filter(user_profile=user_profile,
                                                             message__in=query_result))
        for message in query_result:
            message_ids.append(message.id)
            if user_message_flags.get(message.id) is None:
                user_message_flags[message.id] = ["read", "historical"]
            if is_search:
                search_fields[message.id] = dict([('match_subject', message.match_subject),
                                                  ('match_content', message.match_content)])
    else:
        user_message_flags = dict((user_message.message_id, user_message.flags_list())
                                  for user_message in query_result)
        for user_message in query_result:
            message_ids.append(user_message.message_id)
            if is_search:
                search_fields[user_message.message_id] = \
                    dict([('match_subject', user_message.match_subject),
                          ('match_content', user_message.match_content)])

    cache_transformer = lambda row: Message.build_dict_from_raw_db_row(row, apply_markdown)
    id_fetcher = lambda row: row['id']

    message_dicts = generic_bulk_cached_fetch(lambda message_id: to_dict_cache_key_id(message_id, apply_markdown),
                                              Message.get_raw_db_rows,
                                              message_ids,
                                              id_fetcher=id_fetcher,
                                              cache_transformer=cache_transformer,
                                              extractor=extract_message_dict,
                                              setter=stringify_message_dict)

    message_list = []
    for message_id in message_ids:
        msg_dict = message_dicts[message_id]
        msg_dict.update({"flags": user_message_flags[message_id]})
        msg_dict.update(search_fields.get(message_id, {}))
        message_list.append(msg_dict)

    statsd.incr('loaded_old_messages', len(message_list))
    ret = {'messages': message_list,
           "result": "success",
           "msg": ""}
    return json_success(ret)

def generate_client_id():
    return generate_random_token(32)

@authenticated_json_post_view
def json_get_profile(request, user_profile):
    return get_profile_backend(request, user_profile)

@authenticated_api_view
def api_get_profile(request, user_profile):
    return get_profile_backend(request, user_profile)

def get_profile_backend(request, user_profile):
    result = dict(pointer        = user_profile.pointer,
                  client_id      = generate_client_id(),
                  max_message_id = -1)

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

@authenticated_json_post_view
def json_update_flags(request, user_profile):
    return update_message_flags(request, user_profile);

@has_request_variables
def update_message_flags(request, user_profile, messages=REQ('messages', converter=json_to_list),
                      operation=REQ('op'), flag=REQ('flag'),
                      all=REQ('all', converter=json_to_bool, default=False)):
    do_update_message_flags(user_profile, operation, flag, messages, all)
    return json_success({'result': 'success',
                         'messages': messages,
                         'msg': ''})

@authenticated_api_view
def api_send_message(request, user_profile):
    return send_message_backend(request, user_profile)

@authenticated_json_post_view
def json_send_message(request, user_profile):
    return send_message_backend(request, user_profile)

@authenticated_json_post_view
@has_request_variables
def json_change_enter_sends(request, user_profile,
                            enter_sends=REQ('enter_sends', json_to_bool)):
    do_change_enter_sends(user_profile, enter_sends)
    return json_success()

def is_super_user_api(request):
    return request.user.is_authenticated() and is_super_user(request.user)

def mit_to_mit(user_profile, email):
    # Are the sender and recipient both @mit.edu addresses?
    # We have to handle this specially, inferring the domain from the
    # e-mail address, because the recipient may not existing in Zulip
    # and we may need to make a stub MIT user on the fly.
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = email_to_domain(email)

    return user_profile.realm.domain == "mit.edu" and domain == "mit.edu"

def same_realm_irc_user(user_profile, email):
    # Check whether the target email address is an IRC user in the
    # same realm as user_profile, i.e. if the domain were example.com,
    # the IRC user would need to be username@irc.example.com
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = email_to_domain(email)

    return user_profile.realm.domain == domain.replace("irc.", "")

def same_realm_user(user_profile, email):
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = email_to_domain(email)

    return user_profile.realm.domain == domain

def create_mirrored_message_users(request, user_profile, recipients):
    if "sender" not in request.POST:
        return (False, None)

    sender_email = request.POST["sender"].strip().lower()
    referenced_users = set([sender_email])
    if request.POST['type'] == 'private':
        for email in recipients:
            referenced_users.add(email.lower())

    if request.client.name == "zephyr_mirror":
        user_check = mit_to_mit
        fullname_function = compute_mit_user_fullname
    elif request.client.name == "irc_mirror":
        user_check = same_realm_irc_user
        fullname_function = compute_irc_user_fullname
    elif request.client.name == "jabber_mirror":
        user_check = same_realm_user
        fullname_function = compute_jabber_user_fullname
    else:
        # Unrecognized mirroring client
        return (False, None)

    for email in referenced_users:
        # Check that all referenced users are in our realm:
        if not user_check(user_profile, email):
            return (False, None)

    # Create users for the referenced users, if needed.
    for email in referenced_users:
        create_mirror_user_if_needed(user_profile.realm, email, fullname_function)

    sender = get_user_profile_by_email(sender_email)
    return (True, sender)

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
def json_update_message(request, user_profile):
    return update_message_backend(request, user_profile)

@authenticated_json_post_view
@has_request_variables
def json_fetch_raw_message(request, user_profile,
                           message_id=REQ(converter=to_non_negative_int)):
    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return json_error("No such message")

    if message.sender != user_profile:
        return json_error("Message was not sent by you")

    return json_success({"raw_content": message.content})

@has_request_variables
def update_message_backend(request, user_profile,
                           message_id=REQ(converter=to_non_negative_int),
                           subject=REQ(default=None),
                           propagate_mode=REQ(default="change-one"),
                           content=REQ(default=None)):
    if subject is None and content is None:
        return json_error("Nothing to change")
    do_update_message(user_profile, message_id, subject, propagate_mode, content)
    return json_success()

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
@has_request_variables
def send_message_backend(request, user_profile,
                         message_type_name = REQ('type'),
                         message_to = REQ('to', converter=extract_recipients),
                         forged = REQ(default=False),
                         subject_name = REQ('subject', lambda x: x.strip(), None),
                         message_content = REQ('content'),
                         domain = REQ('domain', default=None)):
    client = request.client
    is_super_user = is_super_user_api(request)
    if forged and not is_super_user:
        return json_error("User not authorized for this query")

    realm = None
    if domain and domain != user_profile.realm.domain:
        if not is_super_user:
            # The email gateway bot needs to be able to send messages in
            # any realm.
            return json_error("User not authorized for this query")
        realm = get_realm(domain)
        if not realm:
            return json_error("Unknown domain " + domain)

    if client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror"]:
        # Here's how security works for mirroring:
        #
        # For private messages, the message must be (1) both sent and
        # received exclusively by users in your realm, and (2)
        # received by the forwarding user.
        #
        # For stream messages, the message must be (1) being forwarded
        # by an API superuser for your realm and (2) being sent to a
        # mirrored stream (any stream for the Zephyr and Jabber
        # mirrors, but only streams with names starting with a "#" for
        # IRC mirrors)
        #
        # The security checks are split between the below code
        # (especially create_mirrored_message_users which checks the
        # same-realm constraint) and recipient_for_emails (which
        # checks that PMs are received by the forwarding user)
        if "sender" not in request.POST:
            return json_error("Missing sender")
        if message_type_name != "private" and not is_super_user:
            return json_error("User not authorized for this query")
        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user_profile, message_to)
        if not valid_input:
            return json_error("Invalid mirrored message")
        if client.name == "zephyr_mirror" and user_profile.realm.domain != "mit.edu":
            return json_error("Invalid mirrored realm")
        if (client.name == "irc_mirror" and message_type_name != "private" and
            not message_to[0].startswith("#")):
            return json_error("IRC stream names must start with #")
        sender = mirror_sender
    else:
        sender = user_profile

    ret = check_send_message(sender, client, message_type_name, message_to,
                             subject_name, message_content, forged=forged,
                             forged_timestamp = request.POST.get('time'),
                             forwarder_user_profile=user_profile, realm=realm)
    return json_success({"id": ret})

@has_request_variables
def render_message_backend(request, user_profile, content=REQ):
    rendered_content = bugdown.convert(content, user_profile.realm.domain)
    return json_success({"rendered": rendered_content})

@authenticated_api_view
def api_get_public_streams(request, user_profile):
    return get_public_streams_backend(request, user_profile)

@authenticated_json_post_view
def json_get_public_streams(request, user_profile):
    return get_public_streams_backend(request, user_profile)

# By default, lists all streams that the user has access to --
# i.e. public streams plus invite-only streams that the user is on
@has_request_variables
def get_streams_backend(request, user_profile,
                        include_public=REQ(converter=json_to_bool, default=True),
                        include_subscribed=REQ(converter=json_to_bool, default=True),
                        include_all_active=REQ(converter=json_to_bool, default=False)):
    if include_all_active and not is_super_user_api(request):
            return json_error("User not authorized for this query")

    # Listing public streams are disabled for some users (e.g. a
    # contractor for CUSTOMER5) and for the mit.edu realm.
    include_public = include_public and not (user_profile.public_streams_disabled or
                                             user_profile.realm.domain == "mit.edu")

    # Only get streams someone is currently subscribed to
    subs_filter = Subscription.objects.filter(active=True).values('recipient_id')
    stream_ids = Recipient.objects.filter(
        type=Recipient.STREAM, id__in=subs_filter).values('type_id')

    # Start out with all active streams in the realm
    query = Stream.objects.filter(id__in = stream_ids, realm=user_profile.realm)

    if not include_all_active:
        user_subs = Subscription.objects.select_related("recipient").filter(
            active=True, user_profile=user_profile,
            recipient__type=Recipient.STREAM)

        if include_subscribed:
            recipient_check = Q(id__in=[sub.recipient.type_id for sub in user_subs])
        if include_public:
            invite_only_check = Q(invite_only=False)

        if include_subscribed and include_public:
            query = query.filter(recipient_check | invite_only_check)
        elif include_public:
            query = query.filter(invite_only_check)
        elif include_subscribed:
            query = query.filter(recipient_check)
        else:
            # We're including nothing, so don't bother hitting the DB.
            query = []

    streams = sorted({"name": stream.name} for stream in query)
    return json_success({"streams": streams})

def get_public_streams_backend(request, user_profile):
    return get_streams_backend(request, user_profile, include_public=True,
                               include_subscribed=False, include_all_active=False)

@authenticated_json_post_view
@has_request_variables
def json_rename_stream(request, user_profile, old_name=REQ, new_name=REQ):
    if not user_profile.has_perm('administer', user_profile.realm):
        return json_error("Insufficient permission to rename stream")

    return json_success(do_rename_stream(user_profile.realm, old_name, new_name))

@authenticated_api_view
def api_list_subscriptions(request, user_profile):
    return list_subscriptions_backend(request, user_profile)

def list_subscriptions_backend(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)[0]})

@transaction.commit_on_success
@has_request_variables
def update_subscriptions_backend(request, user_profile,
                                 delete=REQ(converter=json_to_list, default=[]),
                                 add=REQ(converter=json_to_list, default=[])):
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

@authenticated_api_view
def api_remove_subscriptions(request, user_profile):
    return remove_subscriptions_backend(request, user_profile)

@authenticated_json_post_view
def json_remove_subscriptions(request, user_profile):
    return remove_subscriptions_backend(request, user_profile)

@has_request_variables
def remove_subscriptions_backend(request, user_profile,
                                 streams_raw = REQ("subscriptions", json_to_list)):

    streams, _ = list_to_streams(streams_raw, user_profile)

    result = dict(removed=[], not_subscribed=[])
    (removed, not_subscribed) = bulk_remove_subscriptions([user_profile], streams)
    for (subscriber, stream) in removed:
        result["removed"].append(stream.name)
    for (subscriber, stream) in not_subscribed:
        result["not_subscribed"].append(stream.name)

    return json_success(result)

@authenticated_api_view
def api_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

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

        # The user is not authorized for invite_only streams, and if
        # the user has public streams disabled, nothing is authorized
        if stream.invite_only or user_profile.public_streams_disabled:
            unauthorized_streams.append(stream)

    streams = [stream for stream in streams if
               stream.id not in set(stream.id for stream in unauthorized_streams)]
    return streams, unauthorized_streams

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = REQ("subscriptions", json_to_list),
                              invite_only = REQ(converter=json_to_bool, default=False),
                              announce = REQ(converter=json_to_bool, default=False),
                              principals = REQ(converter=json_to_list, default=None),
                              authorization_errors_fatal = REQ(converter=json_to_bool, default=True)):

    stream_names = []
    for stream in streams_raw:
        if not isinstance(stream, dict):
            return json_error("Malformed request")
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

    # Inform the user if someone else subscribed them to stuff,
    # or if a new stream was created with the "announce" option.
    notifications = []
    if principals and result["subscribed"]:
        for email, subscriptions in result["subscribed"].iteritems():
            if email == user_profile.email:
                # Don't send a Zulip if you invited yourself.
                continue

            if len(subscriptions) == 1:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the%s stream '%s'"
                       % (user_profile.full_name,
                          " **invite-only**" if private_streams[subscriptions[0]] else "",
                          subscriptions[0]))
            else:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the following streams: \n\n"
                       % (user_profile.full_name,))
                for stream in subscriptions:
                    msg += "* %s%s\n" % (
                        stream,
                        " (**invite-only**)" if private_streams[stream] else "")

            if len([s for s in subscriptions if not private_streams[s]]) > 0:
                msg += "\nYou can see historical content on a non-invite-only stream by narrowing to it."
            notifications.append(internal_prep_message("notification-bot@zulip.com",
                                                       "private", email, "", msg))

    if announce and len(created_streams) > 0:
        notifications_stream = user_profile.realm.notifications_stream
        if notifications_stream is not None:
            if len(created_streams) > 1:
                stream_msg = "the following streams: %s" % \
                              (", ".join('`%s`' % (s.name,) for s in created_streams),)
            else:
                stream_msg = "a new stream `%s`" % (created_streams[0].name)
            msg = ("%s just created %s. To join, click the gear "
                   "in the left-side streams list.") % (user_profile.full_name, stream_msg)
            notifications.append(internal_prep_message("notification-bot@zulip.com",
                                   "stream",
                                   notifications_stream.name, "Streams", msg,
                                   realm=notifications_stream.realm))
        else:
            msg = ("Hi there!  %s just created a new stream '%s'. "
                       "To join, click the gear in the left-side streams list."
                       % (user_profile.full_name, created_streams[0].name))
            for realm_user_dict in get_active_user_dicts_in_realm(user_profile.realm):
                # Don't announce to yourself or to people you explicitly added
                # (who will get the notification above instead).
                if realm_user_dict['email'] in principals or realm_user_dict['email'] == user_profile.email:
                    continue
                notifications.append(internal_prep_message("notification-bot@zulip.com",
                                                           "private",
                                                           realm_user_dict['email'], "", msg))

    if len(notifications) > 0:
        do_send_messages(notifications)

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])
    if not authorization_errors_fatal:
        result["unauthorized"] = [stream.name for stream in unauthorized_streams]
    return json_success(result)

@authenticated_api_view
def api_get_members(request, user_profile):
    return get_members_backend(request, user_profile)

@authenticated_json_post_view
def json_get_members(request, user_profile):
    return get_members_backend(request, user_profile)

def get_members_backend(request, user_profile):
    members = [{"full_name": profile.full_name,
                "email": profile.email} for profile in \
                   UserProfile.objects.select_related().filter(realm=user_profile.realm)]
    return json_success({'members': members})

@authenticated_api_view
def api_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

@authenticated_json_post_view
def json_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

@authenticated_json_post_view
@has_request_variables
def json_upload_file(request, user_profile, private=REQ(converter=json_to_bool, default=None)):
    if len(request.FILES) == 0:
        return json_error("You must specify a file to upload")
    if len(request.FILES) != 1:
        return json_error("You may only upload one file at a time")

    user_file = request.FILES.values()[0]
    uri = upload_message_image_through_web_client(request, user_file, user_profile, private=private)
    return json_success({'uri': uri})

@has_request_variables
def get_uploaded_file(request, user_profile, realm_id, filename,
                      redir=REQ(converter=json_to_bool, default=True)):
    if settings.LOCAL_UPLOADS_DIR is not None:
        return HttpResponseForbidden() # Should have been served by nginx

    # Internal users can access all uploads so we can receive attachments in cross-realm messages
    if user_profile.realm.id == int(realm_id) or user_profile.realm.domain == 'zulip.com':
        uri = get_signed_upload_url("%s/%s" % (realm_id, filename))
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
                         old_password=REQ,
                         new_password=REQ,
                         confirm_password=REQ):
    if new_password != "" or confirm_password != "":
        if new_password != confirm_password:
            return json_error("New password must match confirmation password!")
        if not authenticate(username=user_profile.email, password=old_password):
            return json_error("Wrong password!")
        do_change_password(user_profile, new_password)

    result = {}
    if user_profile.full_name != full_name and full_name.strip() != "":
        if user_profile.realm.domain == "users.customer4.invalid":
            # At the request of the facilitators, CUSTOMER4
            # students can't change their names. Failingly silently is
            # fine -- they can't do it through the UI, so they'd have
            # to be trying to break the rules.
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
def json_change_notify_settings(request, user_profile,
                                # enable_desktop_notification needs to default to False
                                # because browsers POST nothing for an unchecked checkbox
                                enable_desktop_notifications=REQ(converter=lambda x: x == "on",
                                                              default=False),
                                enable_sounds=REQ(converter=lambda x: x == "on",
                                                              default=False),
                                enable_offline_email_notifications=REQ(converter=lambda x: x == "on",
                                                                    default=False),
                                enable_offline_push_notifications=REQ(converter=lambda x: x == "on",
                                                                    default=False)):

    result = {}

    if user_profile.enable_desktop_notifications != enable_desktop_notifications:
        do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications)
        result['enable_desktop_notifications'] = enable_desktop_notifications

    if user_profile.enable_sounds != enable_sounds:
        do_change_enable_sounds(user_profile, enable_sounds)
        result['enable_sounds'] = enable_sounds

    if user_profile.enable_offline_email_notifications != enable_offline_email_notifications:
        do_change_enable_offline_email_notifications(user_profile, enable_offline_email_notifications)
        result['enable_offline_email_notifications'] = enable_offline_email_notifications

    if user_profile.enable_offline_push_notifications != enable_offline_push_notifications:
        do_change_enable_offline_push_notifications(user_profile, enable_offline_push_notifications)
        result['enable_offline_push_notifications'] = enable_offline_push_notifications

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_stream_exists(request, user_profile, stream=REQ):
    return stream_exists_backend(request, user_profile, stream)

def stream_exists_backend(request, user_profile, stream_name):
    if not valid_stream_name(stream_name):
        return json_error("Invalid characters in stream name")
    stream = get_stream(stream_name, user_profile.realm)
    result = {"exists": bool(stream)}
    if stream is not None:
        recipient = get_recipient(Recipient.STREAM, stream.id)
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
def json_subscription_property(request, user_profile, stream_name=REQ,
                               property=REQ):
    """
    This is the entry point to accessing or changing subscription
    properties.
    """
    property_converters = dict(color=lambda x: x,
                               in_home_view=json_to_bool,
                               notifications=json_to_bool)
    if property not in property_converters:
        return json_error("Unknown subscription property: %s" % (property,))

    sub = get_subscription_or_die(stream_name, user_profile)[0]
    if request.method == "GET":
        return json_success({'stream_name': stream_name,
                             'value': getattr(sub, property)})
    elif request.method == "POST":
        @has_request_variables
        def do_set_property(request,
                            value=REQ(converter=property_converters[property])):
            do_change_subscription_property(user_profile, sub, stream_name,
                                            property, value)
        do_set_property(request)
        return json_success()
    else:
        return json_error("Invalid verb")

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request, username=REQ, password=REQ):
    user_profile = authenticate(username=username, password=password)
    if user_profile is None:
        return json_error("Your username or password is incorrect.", status=403)
    if not user_profile.is_active:
        return json_error("Your account has been disabled.", status=403)
    return json_success({"api_key": user_profile.api_key})

@authenticated_json_post_view
@has_request_variables
def json_fetch_api_key(request, user_profile, password=REQ):
    if not user_profile.check_password(password):
        return json_error("Your username or password is incorrect.")
    return json_success({"api_key": user_profile.api_key})

class ActivityTable(object):
    def __init__(self, realm, client_name, queries):
        self.realm = realm
        self.summary_mode = realm is None
        self.has_pointer = False
        self.rows = {}

        def do_url(query_name, url):
            fields = [
                'user_profile__realm__domain',
                'user_profile__full_name',
                'user_profile__email',
                'count',
                'last_visit'
            ]

            records = UserActivity.objects.filter(
                    query=url,
                    client__name__startswith=client_name,
                    user_profile__realm__domain=realm
            )
            records = records.select_related().only(*fields)

            count_field = query_name + '_count'
            last_visit_field = query_name + '_last'

            for record in records:
                domain = record.user_profile.realm.domain
                email = record.user_profile.email
                full_name = record.user_profile.full_name
                count = record.count
                last_visit = record.last_visit

                row = self.rows.setdefault(email,
                                           {'realm': domain,
                                            'full_name': full_name,
                                            'email': email,
                                            'type': 'user'})
                row[count_field] = count
                row[last_visit_field] = last_visit


        for query_name, urls in queries:
            if 'pointer' in query_name:
                self.has_pointer = True
            for url in urls:
                do_url(query_name, url)

        for row in self.rows.values():
            # kind of a hack
            last_action = max(v for v in row.values() if isinstance(v, datetime.datetime))
            age = now() - last_action
            if age < datetime.timedelta(minutes=10):
                row['class'] = 'recently_active'
            elif age >= datetime.timedelta(days=1):
                row['class'] = 'long_inactive'
            row['age'] = age

    def sorted_rows(self):
        keyfunc = lambda (k,r): (r['realm'], -1 * r.get('send_message_count', 0))
        return sorted(self.rows.iteritems(), key=keyfunc)

    def content(self):
        return loader.render_to_string('zerver/activity_table.html', dict(table=self))


def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def realm_summary_table(realm_minutes):
    query = '''
        SELECT
            realm.domain,
            coalesce(user_counts.active_user_count, 0) active_user_count,
            (
                SELECT
                    count(*)
                FROM zerver_userprofile up
                WHERE up.realm_id = realm.id
                AND is_active
                AND not is_bot
            ) user_profile_count,
            (
                SELECT
                    count(*)
                FROM zerver_userprofile up
                WHERE up.realm_id = realm.id
                AND is_active
                AND is_bot
            ) bot_count
        FROM zerver_realm realm
        LEFT OUTER JOIN
            (
                SELECT
                    up.realm_id realm_id,
                    count(distinct(ua.user_profile_id)) active_user_count
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    query in (
                        '/json/send_message',
                        '/json/update_pointer'
                    )
                AND
                    last_visit > now() - interval '1 day'
                GROUP BY realm_id
            ) user_counts
            ON user_counts.realm_id = realm.id
        WHERE
            realm.domain not in ('zulip.com', 'customer4.invalid')
        AND EXISTS (
                SELECT *
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    query in (
                        '/json/send_message',
                        '/json/update_pointer'
                    )
                AND
                    up.realm_id = realm.id
                AND
                    last_visit > now() - interval '2 week'
        )
        ORDER BY active_user_count DESC, domain ASC
        '''

    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    # augment data with realm_minutes
    total_hours = 0
    for row in rows:
        domain = row['domain']
        minutes = realm_minutes.get(domain, 0)
        hours = minutes / 60.0
        total_hours += hours
        row['hours'] = str(int(hours))
        try:
            row['hours_per_user'] = '%.1f' % (hours / row['active_user_count'],)
        except:
            pass

    # create totals
    total_active_user_count = 0
    total_user_profile_count = 0
    total_bot_count = 0
    for row in rows:
        total_active_user_count += int(row['active_user_count'])
        total_user_profile_count += int(row['user_profile_count'])
        total_bot_count += int(row['bot_count'])

    rows.append(dict(
        domain='Total',
        active_user_count=total_active_user_count,
        user_profile_count=total_user_profile_count,
        bot_count=total_bot_count,
        hours=int(total_hours)
    ))


    def meets_goal(row):
        # We don't count toward company goals for obvious reasons, and
        # customer4.invalid is essentially a dup for users.customer4.invalid.
        if row['domain'] in ['zulip.com', 'customer4.invalid']:
            return False
        return row['active_user_count'] >= 5

    num_active_sites = len(filter(meets_goal, rows))

    content = loader.render_to_string(
        'zerver/realm_summary_table.html',
        dict(rows=rows, num_active_sites=num_active_sites)
    )
    return dict(content=content)


def user_activity_intervals():
    day_end = timestamp_to_datetime(time.time())
    day_start = day_end - datetime.timedelta(hours=24)

    output = "Per-user online duration for the last 24 hours:\n"
    total_duration = datetime.timedelta(0)

    all_intervals = UserActivityInterval.objects.filter(
        end__gte=day_start,
        start__lte=day_end
    ).select_related(
        'user_profile',
        'user_profile__realm'
    ).only(
        'start',
        'end',
        'user_profile__email',
        'user_profile__realm__domain'
    ).order_by(
        'user_profile__realm__domain',
        'user_profile__email'
    )

    by_domain = lambda row: row.user_profile.realm.domain
    by_email = lambda row: row.user_profile.email

    realm_minutes = {}

    for domain, realm_intervals in itertools.groupby(all_intervals, by_domain):
        realm_duration = datetime.timedelta(0)
        output += '<hr>%s\n' % (domain,)
        for email, intervals in itertools.groupby(realm_intervals, by_email):
            duration = datetime.timedelta(0)
            for interval in intervals:
                start = max(day_start, interval.start)
                end = min(day_end, interval.end)
                duration += end - start

            total_duration += duration
            realm_duration += duration
            output += "  %-*s%s\n" % (37, email, duration, )

        realm_minutes[domain] = realm_duration.total_seconds() / 60

    output += "\nTotal Duration:                      %s\n" % (total_duration,)
    output += "\nTotal Duration in minutes:           %s\n" % (total_duration.total_seconds() / 60.,)
    output += "Total Duration amortized to a month: %s" % (total_duration.total_seconds() * 30. / 60.,)
    content = mark_safe('<pre>' + output + '</pre>')
    return dict(content=content), realm_minutes

def sent_messages_report(realm):
    title = 'Recently sent messages for ' + realm

    cols = [
        'Date',
        'Count'
    ]

    query = '''
        select
            series.day::date,
            q.cnt
        from (
            select generate_series(
                (now()::date - interval '2 week'),
                now()::date,
                interval '1 day'
            ) as day
        ) as series
        left join (
            select
                pub_date::date pub_date,
                count(*) cnt
            from zerver_message m
            join zerver_userprofile up on up.id = m.sender_id
            join zerver_realm r on r.id = up.realm_id
            where
                r.domain = %s
            and
                pub_date > now() - interval '2 week'
            group by
                pub_date::date
            order by
                pub_date::date
        ) q on
            series.day = q.pub_date
    '''
    cursor = connection.cursor()
    cursor.execute(query, [realm])
    rows = cursor.fetchall()
    cursor.close()

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'zerver/ad_hoc_query.html',
        dict(data=data)
    )

    return content

def ad_hoc_queries():
    def get_page(query, cols, title):
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()

        data = dict(
            rows=rows,
            cols=cols,
            title=title
        )

        content = loader.render_to_string(
            'zerver/ad_hoc_query.html',
            dict(data=data)
        )

        return dict(
            content=content,
            title=title
        )

    pages = []

    ###

    title = 'At risk users'

    query = '''
        select
            realm.domain,
            cast(floor(extract(epoch from age(now(), max(last_visit))) / 3600) as int) as age,
            up.email,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where up.is_active
        and (not up.is_bot)
        and domain not in (
            'users.customer4.invalid',
            'ios_appreview.zulip.com',
            'mit.edu'
        )
        and email not like '%%+%%'
        group by up.email, realm.domain
        having max(last_visit) between
            now() - interval '7 day' and
            now() - interval '1 day'
        order by domain, max(last_visit)
    '''

    cols = [
        'Domain',
        'Hours since activity',
        'Email',
        'Hits',
        'Last visit'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Android usage'

    query = '''
        select
            realm.domain,
            up.id user_id,
            client.name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            client.name like 'Android'
        and
            query = 'send_message_backend'
        group by domain, up.id, client.name
        having max(last_visit) > now() - interval '2 week'
        order by domain, up.id, client.name
    '''

    cols = [
        'Domain',
        'User id',
        'Name',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Desktop users'

    query = '''
        select
            realm.domain,
            client.name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            client.name like 'desktop%%'
        group by domain, client.name
        having max(last_visit) > now() - interval '2 week'
        order by domain, client.name
    '''

    cols = [
        'Domain',
        'Client',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Pure API'

    query = '''
        select
            realm.domain,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            query = '/api/v1/send_message'
        and
            client.name = 'API'
        and
            domain != 'zulip.com'
        group by domain
        having max(last_visit) > now() - interval '2 week'
        order by domain
    '''

    cols = [
        'Domain',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Integrations by domain'

    query = '''
        select
            realm.domain,
            case
                when query like '%%external%%' then split_part(query, '/', 5)
                else client.name
            end client_name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            (query = 'send_message_backend'
            and client.name not in ('Android', 'API', 'API: Python')
            and client.name not like 'test: Zulip%%'
            )
        or
            query like '%%external%%'
        group by domain, client_name
        having max(last_visit) > now() - interval '2 week'
        order by domain, client_name
    '''

    cols = [
        'Domain',
        'Client',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Integrations by client'

    query = '''
        select
            case
                when query like '%%external%%' then split_part(query, '/', 5)
                else client.name
            end client_name,
            realm.domain,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            (query = 'send_message_backend'
            and client.name not in ('Android', 'API', 'API: Python')
            and client.name not like 'test: Zulip%%'
            )
        or
            query like '%%external%%'
        group by client_name, domain
        having max(last_visit) > now() - interval '2 week'
        order by client_name, domain
    '''

    cols = [
        'Client',
        'Domain',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    return pages

@zulip_internal
@has_request_variables
def get_activity(request, realm=REQ(default=None)):
    web_queries = (
        ("get_updates",    ["/json/get_updates", "/json/get_events"]),
        ("send_message",   ["/json/send_message"]),
        ("update_pointer", ["/json/update_pointer"]),
    )

    api_queries = (
        ("get_updates",  ["/api/v1/get_messages", "/api/v1/messages/latest", "/api/v1/events"]),
        ("send_message", ["/api/v1/send_message"]),
    )

    if realm is None:
        duration_content, realm_minutes = user_activity_intervals()
        counts_content = realm_summary_table(realm_minutes)
        data = [
            ('Counts', counts_content),
            ('Durations', duration_content),
        ]
        for page in ad_hoc_queries():
            data.append((page['title'], page))
        title = 'Activity'
    else:
        data = [
            ('Website',    ActivityTable(realm, 'website',       web_queries)),
            ('Desktop',    ActivityTable(realm, 'desktop',       web_queries)),
            ('API',        ActivityTable(realm, 'API',           api_queries)),
            ('Android',    ActivityTable(realm, 'Android',       api_queries)),
            ('History',    dict(content=sent_messages_report(realm))),
        ]
        title = '%s activity' % (realm,)

    return render_to_response(
        'zerver/activity.html',
        dict(data=data, realm=realm, title=title),
        context_instance=RequestContext(request)
    )

def get_user_activity_records_for_realm(realm):
    fields = [
        'user_profile__email',
        'query',
        'client__name',
        'count',
        'last_visit',
    ]

    records = UserActivity.objects.filter(
            user_profile__realm__domain=realm
    )
    records = records.order_by("user_profile__email", "-last_visit")
    records = records.select_related('user_profile', 'client').only(*fields)
    return records

def get_user_activity_records_for_email(email):
    fields = [
        'query',
        'client__name',
        'count',
        'last_visit'
    ]

    records = UserActivity.objects.filter(
            user_profile__email=email
    )
    records = records.order_by("-last_visit")
    records = records.select_related('client').only(*fields)
    return records

def raw_user_activity_table(records):
    cols = [
        'query',
        'client',
        'count',
        'last_visit'
    ]

    def row(record):
        return [
                record.query,
                record.client.name,
                record.count,
                record.last_visit
        ]

    rows = map(row, records)

    title = 'Raw Data'

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'zerver/ad_hoc_query.html',
        dict(data=data)
    )
    return content

def get_user_activity_summary(records):
    summary = {}
    def update(action, record):
        if action not in summary:
            summary[action] = dict(
                    count=record.count,
                    last_visit=record.last_visit
            )
        else:
            summary[action]['count'] += record.count
            summary[action]['last_visit'] = max(
                    summary[action]['last_visit'],
                    record.last_visit
            )

    for record in records:
        client = record.client.name
        query = record.query

        if client == 'website':
            update('website', record)
        if query == '/json/send_message':
            update('send', record)
        if query in ['/json/update_pointer', '/api/v1/update_pointer']:
            update('pointer', record)
        update(client, record)


    return summary

def user_activity_summary_table(user_summary):
    rows = []
    for k, v in user_summary.items():
        client = k
        count = v['count']
        last_visit = v['last_visit']
        row = [
                last_visit,
                client,
                count,
        ]
        rows.append(row)

    rows = sorted(rows, key=lambda r: r[0], reverse=True)

    cols = [
            'last_visit',
            'client',
            'count',
    ]

    title = 'User Activity'

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'zerver/ad_hoc_query.html',
        dict(data=data)
    )
    return content

def realm_user_summary_table(all_records):
    user_records = {}

    def by_email(record):
        return record.user_profile.email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def get_last_visit(user_summary, k):
        if k in user_summary:
            return user_summary[k]['last_visit']
        else:
            return None

    rows = []
    for email, user_summary in user_records.items():
        send_time = get_last_visit(user_summary, 'send')
        pointer_time = get_last_visit(user_summary, 'pointer')
        rows.append((email, send_time, pointer_time))

    never = datetime.datetime(1970, 1, 1).replace(tzinfo=utc)
    def by_send_time(row):
        return row[1] or never

    rows = sorted(rows, key=by_send_time, reverse=True)

    cols = [
            'Email',
            'Send',
            'Pointer'
    ]

    title = 'Summary'

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'zerver/ad_hoc_query.html',
        dict(data=data)
    )

    return content

@zulip_internal
def get_realm_activity(request, realm):
    all_records = get_user_activity_records_for_realm(realm)
    all_records = list(all_records)

    data = []
    content = realm_user_summary_table(all_records)

    user_content = dict(content=content)
    data += [('Summary', user_content)]

    realm = None
    title = realm
    return render_to_response(
        'zerver/activity.html',
        dict(data=data, realm=realm, title=title),
        context_instance=RequestContext(request)
    )

@zulip_internal
def get_user_activity(request, email):
    records = get_user_activity_records_for_email(email)

    data = []
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    user_content = dict(content=content)
    data += [('Summary', user_content)]

    content = raw_user_activity_table(records)
    user_content = dict(content=content)
    data += [('Info', user_content)]

    realm = None
    title = email
    return render_to_response(
        'zerver/activity.html',
        dict(data=data, realm=realm, title=title),
        context_instance=RequestContext(request)
    )

def get_status_list(requesting_user_profile):
    return {'presences': get_status_dict(requesting_user_profile),
            'server_timestamp': time.time()}

@authenticated_json_post_view
@has_request_variables
def json_update_active_status(request, user_profile, status=REQ,
                              new_user_input=REQ(converter=json_to_bool, default=False)):
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
def json_get_active_statuses(request, user_profile):
    return json_success(get_status_list(user_profile))

# Read the source map information for decoding JavaScript backtraces
js_source_map = None
if not (settings.DEBUG or settings.TEST_SUITE):
    js_source_map = SourceMap(os.path.join(
        settings.DEPLOY_ROOT, 'prod-static/source-map'))

@authenticated_json_post_view
@has_request_variables
def json_report_error(request, user_profile, message=REQ, stacktrace=REQ,
                      ui_message=REQ(converter=json_to_bool), user_agent=REQ,
                      href=REQ, log=REQ,
                      more_info=REQ(converter=json_to_dict, default=None)):
    subject = "error for %s" % (user_profile.email,)
    if ui_message:
        subject = "User-visible browser " + subject
    else:
        subject = "Browser " + subject

    if js_source_map:
        stacktrace = js_source_map.annotate_stacktrace(stacktrace)

    body = ("Message:\n%s\n\nStacktrace:\n%s\n\nUser agent: %s\nhref: %s\n"
            "User saw error in UI: %s\n"
            % (message, stacktrace, user_agent, href, ui_message))

    body += "Server path: %s\n" % (settings.DEPLOY_ROOT,)
    try:
        body += "Deployed version: %s" % (
            subprocess.check_output(["git", "log", "HEAD^..HEAD", "--oneline"]),)
    except Exception:
        body += "Could not determine current git commit ID.\n"

    if more_info is not None:
        body += "\nAdditional information:"
        for (key, value) in more_info.iteritems():
            body += "\n  %s: %s" % (key, value)

    body += "\n\nLog:\n%s" % (log,)

    mail_admins(subject, body)
    return json_success()

@authenticated_json_post_view
def json_events_register(request, user_profile):
    return events_register_backend(request, user_profile)

# Does not need to be authenticated because it's called from rest_dispatch
@has_request_variables
def api_events_register(request, user_profile,
                        apply_markdown=REQ(default=False, converter=json_to_bool),
                        all_public_streams=REQ(default=False, converter=json_to_bool)):
    return events_register_backend(request, user_profile,
                                   apply_markdown=apply_markdown,
                                   all_public_streams=all_public_streams)

@has_request_variables
def events_register_backend(request, user_profile, apply_markdown=True,
                            all_public_streams=False,
                            event_types=REQ(converter=json_to_list, default=None),
                            queue_lifespan_secs=REQ(converter=int, default=0)):
    ret = do_events_register(user_profile, request.client, apply_markdown,
                             event_types, queue_lifespan_secs, all_public_streams)
    return json_success(ret)

@authenticated_json_post_view
def json_messages_in_narrow(request, user_profile):
    return messages_in_narrow_backend(request, user_profile)

@has_request_variables
def messages_in_narrow_backend(request, user_profile, msg_ids = REQ(converter=json_to_list),
                               narrow = REQ(converter=narrow_parameter)):
    # Note that this function will only work on messages the user
    # actually received

    query = UserMessage.objects.select_related("message") \
                               .filter(user_profile=user_profile, message__id__in=msg_ids)
    build = NarrowBuilder(user_profile, "message__")
    for operator, operand in narrow:
        query = build(query, operator, operand)

    return json_success({"messages": dict((msg.message.id,
                                           {'match_subject': msg.match_subject,
                                            'match_content': msg.match_content})
                                          for msg in query.iterator())})

def deactivate_user_backend(request, user_profile, email):
    try:
        target = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return json_error('No such user')

    if not user_profile.can_admin_user(target):
        return json_error('Insufficient permission')

    do_deactivate(target)
    return json_success({})

@has_request_variables
def patch_bot_backend(request, user_profile, email, full_name=REQ):
    # TODO:
    #   1) Validate data
    #   2) Support avatar changes
    try:
        bot = get_user_profile_by_email(email)
    except:
        return json_error('No such user')

    if not user_profile.can_admin_user(bot):
        return json_error('Insufficient permission')

    do_change_full_name(bot, full_name)

    bot_avatar_url = None

    if len(request.FILES) == 0:
        pass
    elif len(request.FILES) == 1:
        user_file = request.FILES.values()[0]
        upload_avatar_image(user_file, user_profile, bot.email)
        avatar_source = UserProfile.AVATAR_FROM_USER
        bot.avatar_source = avatar_source
        bot.save(update_fields=["avatar_source"])
        bot_avatar_url = avatar_url(bot)
    else:
        return json_error("You may only upload one file at a time")

    json_result = dict(
        full_name = full_name,
        avatar_url = bot_avatar_url
    )
    return json_success(json_result)

@authenticated_json_post_view
def json_set_avatar(request, user_profile):
    if len(request.FILES) != 1:
        return json_error("You must upload exactly one avatar.")

    user_file = request.FILES.values()[0]
    upload_avatar_image(user_file, user_profile, user_profile.email)
    user_profile.avatar_source = UserProfile.AVATAR_FROM_USER
    user_profile.save(update_fields=["avatar_source"])
    user_avatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = user_avatar_url
    )
    return json_success(json_result)

@has_request_variables
def regenerate_api_key(request, user_profile):
    user_profile.api_key = random_api_key()
    user_profile.save(update_fields=["api_key"])
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

    bot.api_key = random_api_key()
    bot.save(update_fields=["api_key"])
    json_result = dict(
        api_key = bot.api_key
    )
    return json_success(json_result)

@authenticated_json_post_view
@has_request_variables
def json_create_bot(request, user_profile, full_name=REQ, short_name=REQ):
    short_name += "-bot"
    email = short_name + "@" + user_profile.realm.domain
    form = CreateBotForm({'full_name': full_name, 'email': email})
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

    bot_profile = do_create_user(email, '', user_profile.realm, full_name,
                                 short_name, True, True,
                                 user_profile, avatar_source)
    json_result = dict(
            api_key=bot_profile.api_key,
            avatar_url=avatar_url(bot_profile)
    )
    return json_success(json_result)

@authenticated_json_post_view
def json_get_bots(request, user_profile):
    bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                              bot_owner=user_profile)
    bot_profiles = bot_profiles.order_by('date_joined')

    def bot_info(bot_profile):
        return dict(
                username   = bot_profile.email,
                full_name  = bot_profile.full_name,
                api_key    = bot_profile.api_key,
                avatar_url = avatar_url(bot_profile)
        )

    return json_success({'bots': map(bot_info, bot_profiles)})

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
                         alert_words=REQ(converter=json_to_list, default=[])):
    do_set_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def set_alert_words(request, user_profile,
                    alert_words=REQ(converter=json_to_list, default=[])):
    do_set_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def add_alert_words(request, user_profile,
                    alert_words=REQ(converter=json_to_list, default=[])):
    do_add_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def remove_alert_words(request, user_profile,
                       alert_words=REQ(converter=json_to_list, default=[])):
    do_remove_alert_words(user_profile, alert_words)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_set_muted_topics(request, user_profile,
                         muted_topics=REQ(converter=json_to_list, default=[])):
    do_set_muted_topics(user_profile, muted_topics)
    return json_success()

@has_request_variables
def add_apns_device_token(request, user_profile, token=REQ):
    if token == '' or len(token) > 255:
        return json_error('Empty or invalid length APNS token')

    # The iOS app receives the token on each startup, so overwrite with our
    # latest value
    token, created = AppleDeviceToken.objects.get_or_create(user=user_profile, token=token)
    if not created:
        token.last_updated = now()
        token.save(update_fields=['last_updated'])

    return json_success()

@has_request_variables
def remove_apns_device_token(request, user_profile, token=REQ):
    if token == '' or len(token) > 255:
        return json_error('Empty or invalid length APNS token')

    try:
        apns_token = AppleDeviceToken.objects.get(token=token)
        apns_token.delete()
    except AppleDeviceToken.DoesNotExist:
        return json_error("APNS token does not exist")

    return json_success()
