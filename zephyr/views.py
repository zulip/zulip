from __future__ import absolute_import

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext, loader
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.core import validators
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.db.models import Q, F
from django.core.mail import send_mail, mail_admins
from django.db import transaction
from django.template.defaultfilters import slugify
from zephyr.models import Message, UserProfile, Stream, Subscription, \
    Recipient, Realm, UserMessage, \
    PreregistrationUser, get_client, MitUser, UserActivity, \
    MAX_SUBJECT_LENGTH, get_stream, UserPresence, \
    get_recipient, valid_stream_name, to_dict_cache_key, to_dict_cache_key_id
from zephyr.lib.actions import do_add_subscription, do_remove_subscription, \
    do_change_password, create_mit_user_if_needed, do_change_full_name, \
    do_change_enable_desktop_notifications, do_change_enter_sends, do_change_enable_sounds, \
    do_send_confirmation_email, do_activate_user, do_create_user, check_send_message, \
    log_subscription_property_change, internal_send_message, \
    create_stream_if_needed, gather_subscriptions, subscribed_to_stream, \
    update_user_presence, bulk_add_subscriptions, update_message_flags, \
    recipient_for_emails, extract_recipients, do_events_register, do_finish_tutorial, \
    get_status_dict, do_change_enable_offline_email_notifications, \
    do_update_onboarding_steps
from zephyr.forms import RegistrationForm, HomepageForm, ToSForm, CreateBotForm, \
    is_unique, is_inactive, isnt_mit
from django.views.decorators.csrf import csrf_exempt
from django_openid_auth.views import default_render_failure, login_complete, parse_openid_response
from openid.consumer.consumer import SUCCESS as openid_SUCCESS
from openid.extensions import ax

from zephyr.decorator import require_post, \
    authenticated_api_view, authenticated_json_post_view, \
    has_request_variables, authenticated_json_view, \
    to_non_negative_int, json_to_dict, json_to_list, json_to_bool, \
    JsonableError, RequestVariableMissingError, get_user_profile_by_email, \
    authenticated_rest_api_view, process_as_post, REQ
from zephyr.lib.query import last_n
from zephyr.lib.avatar import gravatar_hash
from zephyr.lib.response import json_success, json_error, json_response, json_method_not_allowed
from zephyr.lib.timestamp import datetime_to_timestamp
from zephyr.lib.cache import cache_with_key, cache_get_many, cache_set_many
from zephyr.lib.unminify import SourceMap
from zephyr.lib.queue import queue_json_publish
from zephyr.lib.utils import statsd
from zephyr import tornado_callbacks

from confirmation.models import Confirmation


import datetime
import simplejson
import re
import urllib
import os
import base64
import time
import logging
from mimetypes import guess_type, guess_extension
from os import path
from functools import wraps
from collections import defaultdict

from boto.s3.key import Key
from boto.s3.connection import S3Connection

from defusedxml.ElementTree import fromstring as xml_fromstring

def list_to_streams(streams_raw, user_profile, autocreate=False, invite_only=False):
    """Converts plaintext stream names to a list of Streams, validating input in the process

    For each stream name, we validate it to ensure it meets our requirements for a proper
    stream name: that is, that it is shorter than 30 characters and passes valid_stream_name.

    We also ensure the stream is visible to the user_profile who made the request; a call
    to list_to_streams will fail if one of the streams is invite_only and user_profile
    is not already on the stream.

    This function in autocreate mode should be atomic: either an exception will be raised
    during a precheck, or all the streams specified will have been created if applicable.

    @param streams_raw The list of stream names to process
    @param user_profile The user for whom we are retreiving the streams
    @param autocreate Whether we should create streams if they don't already exist
    @param invite_only Whether newly created streams should have the invite_only bit set
    """
    streams = []
    # Validate all streams, getting extant ones, then get-or-creating the rest.
    stream_set = set(stream_name.strip() for stream_name in streams_raw)
    rejects = []
    for stream_name in stream_set:
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            raise JsonableError("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            raise JsonableError("Invalid stream name (%s)." % (stream_name,))
        stream = get_stream(stream_name, user_profile.realm)

        if stream is None:
            rejects.append(stream_name)
        else:
            streams.append(stream)
            # Verify we can access the stream
            if stream.invite_only and not subscribed_to_stream(user_profile, stream):
                raise JsonableError("Unable to access invite-only stream (%s)." % stream.name)
    if autocreate:
        for stream_name in rejects:
            stream, created = create_stream_if_needed(user_profile.realm,
                                                 stream_name,
                                                 invite_only=invite_only)
            streams.append(stream)
    elif rejects:
        raise JsonableError("Stream(s) (%s) do not exist" % ", ".join(rejects))

    return streams

def send_signup_message(sender, signups_stream, user_profile, internal=False):
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    internal_send_message(sender,
            "stream", signups_stream, user_profile.realm.domain,
            "%s <`%s`> just signed up for Humbug!%s(total: **%i**)" % (
                user_profile.full_name,
                user_profile.email,
                internal_blurb,
                UserProfile.objects.filter(realm=user_profile.realm,
                                           is_active=True).count(),
                )
            )

def notify_new_user(user_profile, internal=False):
    send_signup_message("humbug+signups@humbughq.com", "signups", user_profile, internal)
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
        or agent.realm.domain == 'mit.edu'
        or agent.realm != principal_user_profile.realm):
        # We have to make sure we don't leak information about which users
        # are registered for Humbug in a different realm.  We could do
        # something a little more clever and check the domain part of the
        # principal to maybe give a better error message
        raise PrincipalError(principal)

    return principal_user_profile

METHODS = ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH')

@csrf_exempt
def rest_dispatch(request, **kwargs):
    supported_methods = {}
    # duplicate kwargs so we can mutate the original as we go
    for arg in list(kwargs):
        if arg in METHODS:
            supported_methods[arg] = kwargs[arg]
            del kwargs[arg]
    if request.method in supported_methods.keys():
        target_function = globals()[supported_methods[request.method]]
        target_function = authenticated_rest_api_view(target_function)
        if request.method not in ["GET", "POST"]:
            # process_as_post needs to be the outer decorator, because
            # otherwise we might access and thus cache a value for
            # request.REQUEST.
            target_function = process_as_post(target_function)
        return target_function(request, **kwargs)
    return json_method_not_allowed(supported_methods.keys())

@require_post
@has_request_variables
def beta_signup_submission(request, name=REQ, email=REQ,
                           company=REQ, count=REQ, product=REQ):
    content = """Name: %s
Email: %s
Company: %s
# users: %s
Currently using: %s""" % (name, email, company, count, product,)
    subject = "Interest in Humbug: %s" % company
    from_email = '"%s" via Web <humbug+signups@humbughq.com>' % (name,)
    to_email = '"Humbug Signups" <humbug+signups@humbughq.com>'
    send_mail(subject, content, from_email, [to_email])
    return json_success()

@require_post
def accounts_register(request):
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    mit_beta_user = isinstance(confirmation.content_object, MitUser)

    # If someone invited you, you are joining their realm regardless
    # of your e-mail address.
    #
    # MitUsers can't be referred and don't have a referred_by field.
    if not mit_beta_user and prereg_user.referred_by:
        domain = prereg_user.referred_by.realm.domain
    else:
        domain = email.split('@')[-1]

    try:
        if mit_beta_user:
            # MIT users already exist, but are supposed to be inactive.
            is_inactive(email)
        else:
            # Other users should not already exist at all.
            is_unique(email)
    except ValidationError:
        return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + urllib.quote_plus(email))

    if request.POST.get('from_confirmation'):
        form = RegistrationForm()
    else:
        form = RegistrationForm(request.POST)
        if form.is_valid():
            password   = form.cleaned_data['password']
            full_name  = form.cleaned_data['full_name']
            short_name = email.split('@')[0]
            (realm, _) = Realm.objects.get_or_create(domain=domain)

            # FIXME: sanitize email addresses and fullname
            if mit_beta_user:
                user_profile = get_user_profile_by_email(email)
                do_activate_user(user_profile)
                do_change_password(user_profile, password)
                do_change_full_name(user_profile, full_name)
            else:
                user_profile = do_create_user(email, password, realm, full_name, short_name)
                if prereg_user.referred_by is not None:
                    # This is a cross-realm private message.
                    internal_send_message("humbug+signups@humbughq.com",
                            "private", prereg_user.referred_by.email, user_profile.realm.domain,
                            "%s <`%s`> accepted your invitation to join Humbug!" % (
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
            return HttpResponseRedirect(reverse('zephyr.views.home'))

    return render_to_response('zephyr/register.html',
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
    company_name = email.split('@')[-1]
    if request.method == "POST":
        form = ToSForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            send_mail('Terms acceptance for ' + full_name,
                    loader.render_to_string('zephyr/tos_accept_body.txt',
                        {'name': full_name,
                         'email': email,
                         'ip': request.META['REMOTE_ADDR'],
                         'browser': request.META['HTTP_USER_AGENT']}),
                        "humbug@humbughq.com",
                        ["all@humbughq.com"])
            do_change_full_name(request.user, full_name)
            return redirect(home)

    else:
        form = ToSForm()
    return render_to_response('zephyr/accounts_accept_terms.html',
        { 'form': form, 'company_name': company_name, 'email': email },
        context_instance=RequestContext(request))

def api_endpoint_docs(request):
    raw_calls = open('templates/zephyr/api_content.json', 'r').read()
    calls = simplejson.loads(raw_calls)
    langs = set()
    for call in calls:
        for example_type in ('request', 'response'):
            for lang in call.get('example_' + example_type, []):
                langs.add(lang)
    return render_to_response(
            'zephyr/api_endpoints.html', {
                'content': calls,
                'langs': langs,
                },
        context_instance=RequestContext(request))

@authenticated_json_post_view
@has_request_variables
def json_invite_users(request, user_profile, invitee_emails=REQ):
    # Validation
    if settings.ALLOW_REGISTER == False:
        try:
            isnt_mit(user_profile.email)
        except ValidationError:
            return json_error("Invitations are not enabled for MIT at this time.")

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

    new_prereg_users = []
    errors = []
    skipped = []
    for email in invitee_emails:
        if email == '':
            continue

        if not validators.email_re.match(email):
            errors.append((email, "Invalid address."))
            continue

        if user_profile.realm.restricted_to_domain and \
                email.split('@', 1)[-1].lower() != user_profile.realm.domain.lower():
            errors.append((email, "Outside your domain."))
            continue

        # Redundant check in case earlier validation preventing MIT users from
        # inviting people fails.
        if settings.ALLOW_REGISTER == False:
            try:
                isnt_mit(email)
            except ValidationError:
                errors.append((email, "Invitations are not enabled for MIT at this time."))
                continue

        try:
            is_unique(email)
        except ValidationError:
            skipped.append((email, "Already has an account."))
            continue

        # The logged in user is the referrer.
        prereg_user = PreregistrationUser(email=email, referred_by=user_profile)

        # We save twice because you cannot associate a ManyToMany field
        # on an unsaved object.
        prereg_user.save()
        prereg_user.streams = streams
        prereg_user.save()

        new_prereg_users.append(prereg_user)

    if errors:
        return json_error(data={'errors': errors},
                          msg="Some emails did not validate, so we didn't send any invitations.")

    if skipped and len(skipped) == len(invitee_emails):
        # All e-mails were skipped, so we didn't actually invite anyone.
        return json_error(data={'errors': skipped},
                          msg="We weren't able to invite anyone.")

    # If we encounter an exception at any point before now, there are no unwanted side-effects,
    # since it is totally fine to have duplicate PreregistrationUsers
    for user in new_prereg_users:
        event = {"email": user.email, "referrer_email": user_profile.email}
        queue_json_publish("invites", event,
                           lambda event: do_send_confirmation_email(user, user_profile))

    if skipped:
        return json_error(data={'errors': skipped},
                          msg="Some of those addresses are already using Humbug, \
so we didn't send them an invitation. We did send invitations to everyone else!")
    else:
        return json_success()

def handle_openid_errors(request, issue, openid_response=None):
    if issue == "Unknown user":
        if openid_response is not None and openid_response.status == openid_SUCCESS:
            ax_response = ax.FetchResponse.fromSuccessResponse(openid_response)
            google_email = openid_response.getSigned('http://openid.net/srv/ax/1.0', 'value.email')
            full_name = " ".join((
                    ax_response.get('http://axschema.org/namePerson/first')[0],
                    ax_response.get('http://axschema.org/namePerson/last')[0]))
            form = HomepageForm({'email': google_email})
            request.verified_email = None
            if form.is_valid():
                # Construct a PreregistrationUser object and send the user over to
                # the confirmation view.
                prereg_user = PreregistrationUser()
                prereg_user.email = google_email
                prereg_user.save()
                return redirect("".join((
                    "/",
                    # Split this so we only get the part after the /
                    Confirmation.objects.get_link_for_object(prereg_user).split("/", 3)[3],
                    '?gafyd_name=',
                    urllib.quote_plus(full_name))))
            else:
                return render_to_response('zephyr/accounts_home.html', {'form': form})
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

@require_post
def logout_then_login(request, **kwargs):
    return django_logout_then_login(request, kwargs)

def accounts_home(request):
    if request.method == 'POST':
        form = HomepageForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            prereg_user = PreregistrationUser()
            prereg_user.email = email
            prereg_user.save()
            Confirmation.objects.send_confirmation(prereg_user, email)
            return HttpResponseRedirect(reverse('send_confirm', kwargs={'email': email}))
        try:
            email = request.POST['email']
            # Note: We don't check for uniqueness
            is_inactive(email)
        except ValidationError:
            return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + urllib.quote_plus(email))
    else:
        form = HomepageForm()
    return render_to_response('zephyr/accounts_home.html', {'form': form},
                              context_instance=RequestContext(request))

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def home(request):
    # We need to modify the session object every two weeks or it will expire.
    # This line makes reloading the page a sufficient action to keep the
    # session alive.
    request.session.modified = True

    user_profile = request.user

    register_ret = do_events_register(user_profile, get_client("website"),
                                      apply_markdown=True)
    user_has_messages = (register_ret['max_message_id'] != -1)

    # Brand new users get the tutorial
    needs_tutorial = settings.TUTORIAL_ENABLED and \
        user_profile.tutorial_status == UserProfile.TUTORIAL_WAITING

    # If the user has previously started (but not completed) the tutorial,
    # finish it for her and subscribe her to the default streams
    if user_profile.tutorial_status == UserProfile.TUTORIAL_STARTED:
        tutorial_stream = user_profile.tutorial_stream_name()
        try:
            stream = Stream.objects.get(realm=user_profile.realm, name=tutorial_stream)
            do_remove_subscription(user_profile, stream)
        except Stream.DoesNotExist:
            pass

        do_finish_tutorial(user_profile)

    if user_profile.pointer == -1 and user_has_messages:
        # Put the new user's pointer at the bottom
        #
        # This improves performance, because we limit backfilling of messages
        # before the pointer.  It's also likely that someone joining an
        # organization is interested in recent messages more than the very
        # first messages on the system.

        user_profile.pointer = register_ret['max_message_id']
        user_profile.last_pointer_updater = request.session.session_key

    # Pass parameters to the client-side JavaScript code.
    # These end up in a global JavaScript Object named 'page_params'.
    page_params = simplejson.encoder.JSONEncoderForHTML().encode(dict(
        debug_mode            = settings.DEBUG,
        poll_timeout          = settings.POLL_TIMEOUT,
        have_initial_messages = user_has_messages,
        stream_list           = register_ret['subscriptions'],
        people_list           = register_ret['realm_users'],
        initial_pointer       = register_ret['pointer'],
        initial_presences     = register_ret['presences'],
        initial_servertime    = time.time(), # Used for calculating relative presence age
        fullname              = user_profile.full_name,
        email                 = user_profile.email,
        domain                = user_profile.realm.domain,
        enter_sends           = user_profile.enter_sends,
        needs_tutorial        = needs_tutorial,
        desktop_notifications_enabled =
            user_profile.enable_desktop_notifications,
        sounds_enabled =
            user_profile.enable_sounds,
        enable_offline_email_notifications =
            user_profile.enable_offline_email_notifications,
        event_queue_id        = register_ret['queue_id'],
        last_event_id         = register_ret['last_event_id'],
        max_message_id        = register_ret['max_message_id'],
        onboarding_steps      = simplejson.loads(user_profile.onboarding_steps)
    ))

    statsd.incr('views.home')

    try:
        isnt_mit(user_profile.email)
        show_invites = True
    except ValidationError:
        show_invites = settings.ALLOW_REGISTER

    return render_to_response('zephyr/index.html',
                              {'user_profile': user_profile,
                               'page_params' : page_params,
                               'email_hash'  : gravatar_hash(user_profile.email),
                               'full_handlebars': not settings.PIPELINE,
                               'show_debug':
                                   settings.DEBUG and ('show_debug' in request.GET),
                               'show_invites': show_invites
                               },
                              context_instance=RequestContext(request))

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
    return get_old_messages_backend(request, user_profile,
                                    apply_markdown=True)

@authenticated_api_view
@has_request_variables
def api_get_old_messages(request, user_profile,
                         apply_markdown=REQ(default=False,
                                            converter=simplejson.loads)):
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
        if operand == 'private-message':
            return (self.pQ(recipient__type=Recipient.PERSONAL) |
                    self.pQ(recipient__type=Recipient.HUDDLE))
        elif operand == 'starred':
            return Q(flags=UserMessage.flags.starred)
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    def by_stream(self, operand):
        stream = get_stream(operand, self.user_profile.realm)
        if stream is None:
            raise BadNarrowOperator('unknown stream ' + operand)
        recipient = get_recipient(Recipient.STREAM, type_id=stream.id)
        return self.pQ(recipient=recipient)

    def by_subject(self, operand):
        return self.pQ(subject__iexact=operand)

    def by_sender(self, operand):
        return self.pQ(sender__email__iexact=operand)

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
            tsquery = "plainto_tsquery('humbug.english_us_search', %s)"
            where = "search_tsvector @@ " + tsquery
            match_content = "ts_headline('humbug.english_us_search', rendered_content, " \
                + tsquery + ", 'StartSel=\"<span class=\"\"highlight\"\">\", StopSel=</span>, " \
                "HighlightAll=TRUE')"
            # We HTML-escape the subject in Postgres to avoid doing a server round-trip
            match_subject = "ts_headline('humbug.english_us_search', escape_html(subject), " \
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
                             apply_markdown=True):
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

    num_extra_messages = 1
    is_search = False

    if narrow is not None:
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
    if num_before != 0 and num_after == 0:
        num_before += num_extra_messages
        query_result = last_n(num_before, query.filter(**add_prefix(id__lte=anchor)))
    elif num_before == 0 and num_after != 0:
        num_after += num_extra_messages
        query_result = query.filter(**add_prefix(id__gte=anchor))[:num_after]
    else:
        num_after += num_extra_messages
        query_result = (last_n(num_before, query.filter(**add_prefix(id__lt=anchor)))
                    + list(query.filter(**add_prefix(id__gte=anchor))[:num_after]))

    # The following is a little messy, but ensures that the code paths
    # are similar regardless of the value of include_history.  The
    # 'user_messages' dictionary maps each message to the user's
    # UserMessage object for that message, which we will attach to the
    # rendered message dict before returning it.  We attempt to
    # bulk-fetch rendered message dicts from memcached using the
    # 'messages' list.
    search_fields = dict()
    message_ids = []
    if include_history:
        user_messages = dict((user_message.message_id, user_message) for user_message in
                             UserMessage.objects.filter(user_profile=user_profile,
                                                        message__in=query_result))
        for message in query_result:
            message_ids.append(message.id)
            if is_search:
                search_fields[message.id] = dict([('match_subject', message.match_subject),
                                                  ('match_content', message.match_content)])
    else:
        user_messages = dict((user_message.message_id, user_message)
                             for user_message in query_result)
        for user_message in query_result:
            message_ids.append(user_message.message_id)
            if is_search:
                search_fields[user_message.message_id] = \
                    dict([('match_subject', user_message.match_subject),
                          ('match_content', user_message.match_content)])

    bulk_messages = cache_get_many([to_dict_cache_key_id(message_id, apply_markdown)
                                    for message_id in message_ids])

    needed_ids = [message_id for message_id in message_ids if
                  to_dict_cache_key_id(message_id, apply_markdown) not in bulk_messages]
    if len(needed_ids) > 0:
        full_messages = Message.objects.select_related().filter(id__in=needed_ids)

        items_for_memcached = {}
        for message in full_messages:
            key = to_dict_cache_key(message, apply_markdown)
            if bulk_messages.get(key) is None:
                elt = message.to_dict_uncached(apply_markdown)
                items_for_memcached[key] = (elt,)
                bulk_messages[key] = (elt,)
        if len(items_for_memcached) > 0:
            cache_set_many(items_for_memcached)

    message_list = []
    for message_id in message_ids:
        if include_history:
            flags_dict = {'flags': ["read", "historical"]}
        if message_id in user_messages:
            flags_dict = user_messages[message_id].flags_dict()
        elt = bulk_messages.get(to_dict_cache_key_id(message_id, apply_markdown))[0]
        msg_dict = dict(elt)
        msg_dict.update(flags_dict)
        msg_dict.update(search_fields.get(elt['id'], {}))
        message_list.append(msg_dict)

    statsd.incr('loaded_old_messages', len(message_list))
    ret = {'messages': message_list,
           "result": "success",
           "msg": ""}
    return json_success(ret)

def generate_client_id():
    return base64.b16encode(os.urandom(16)).lower()

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
@has_request_variables
def json_update_flags(request, user_profile, messages=REQ('messages', converter=json_to_list),
                      operation=REQ('op'), flag=REQ('flag'),
                      all=REQ('all', converter=json_to_bool, default=False)):
    update_message_flags(user_profile, operation, flag, messages, all)
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

@authenticated_json_post_view
@has_request_variables
def json_update_onboarding_steps(request, user_profile,
                                 onboarding_steps=REQ(converter=json_to_list,
                                                      default=[])):
    do_update_onboarding_steps(user_profile, onboarding_steps)
    return json_success()

# Currently tabbott/extra@mit.edu is our only superuser.  TODO: Make
# this a real superuser security check.
def is_super_user_api(request):
    return request.user.is_authenticated() and request.user.email == "tabbott/extra@mit.edu"

def mit_to_mit(user_profile, email):
    # Are the sender and recipient both @mit.edu addresses?
    # We have to handle this specially, inferring the domain from the
    # e-mail address, because the recipient may not existing in Humbug
    # and we may need to make a stub MIT user on the fly.
    if not validators.email_re.match(email):
        return False

    if user_profile.realm.domain != "mit.edu":
        return False

    domain = email.split("@", 1)[1]
    return user_profile.realm.domain == domain

def create_mirrored_message_users(request, user_profile, recipients):
    if "sender" not in request.POST:
        return (False, None)

    sender_email = request.POST["sender"].strip().lower()
    referenced_users = set([sender_email])
    if request.POST['type'] == 'private':
        for email in recipients:
            referenced_users.add(email.lower())

    # Check that all referenced users are in our realm:
    for email in referenced_users:
        if not mit_to_mit(user_profile, email):
            return (False, None)

    # Create users for the referenced users, if needed.
    for email in referenced_users:
        create_mit_user_if_needed(user_profile.realm, email)

    sender = get_user_profile_by_email(sender_email)
    return (True, sender)

@authenticated_json_post_view
@has_request_variables
def json_tutorial_send_message(request, user_profile,
                               message_type_name = REQ('type'),
                               subject_name = REQ('subject', lambda x: x.strip(), None),
                               message_content = REQ('content')):
    """
    This function, used by the onboarding tutorial, causes the
    Tutorial Bot to send you the message you pass in here.
    (That way, the Tutorial Bot's messages to you get rendered
     by the server and therefore look like any other message.)
    """
    sender_name = "humbug+tutorial@humbughq.com"
    if message_type_name == 'private':
        # For now, we discard the recipient on PMs; the tutorial bot
        # can only send to you.
        internal_send_message(sender_name,
                              "private",
                              user_profile.email,
                              "",
                              message_content,
                              realm=user_profile.realm)
        return json_success()
    elif message_type_name == 'stream':
        tutorial_stream_name = user_profile.tutorial_stream_name()
        ## TODO: For open realms, we need to use the full name here,
        ## so that me@gmail.com and me@hotmail.com don't get the same stream.
        internal_send_message(sender_name,
                              "stream",
                              tutorial_stream_name,
                              subject_name,
                              message_content,
                              realm=user_profile.realm)
        return json_success()
    return json_error('Bad data passed in to tutorial_send_message')


@authenticated_json_post_view
@has_request_variables
def json_tutorial_status(request, user_profile, status=REQ('status')):
    if status == 'started':
        user_profile.tutorial_status = UserProfile.TUTORIAL_STARTED
        user_profile.save()
    elif status == 'finished':
        do_finish_tutorial(user_profile)

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
                         message_content = REQ('content')):
    client = request.client
    is_super_user = is_super_user_api(request)
    if forged and not is_super_user:
        return json_error("User not authorized for this query")

    if client.name == "zephyr_mirror":
        # Here's how security works for non-superuser mirroring:
        #
        # The message must be (1) a private message (2) that
        # is both sent and received exclusively by other users in your
        # realm which (3) must be the MIT realm and (4) you must have
        # received the message.
        #
        # If that's the case, we let it through, but we still have the
        # security flaw that we're trusting your Hesiod data for users
        # you report having sent you a message.
        if "sender" not in request.POST:
            return json_error("Missing sender")
        if message_type_name != "private" and not is_super_user:
            return json_error("User not authorized for this query")
        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user_profile, message_to)
        if not valid_input:
            return json_error("Invalid mirrored message")
        if user_profile.realm.domain != "mit.edu":
            return json_error("Invalid mirrored realm")
        sender = mirror_sender
    else:
        sender = user_profile

    ret = check_send_message(sender, client, message_type_name, message_to,
                             subject_name, message_content, forged=forged,
                             forged_timestamp = request.POST.get('time'),
                             forwarder_user_profile=user_profile)
    if ret is not None:
        return json_error(ret)
    return json_success()

@authenticated_api_view
def api_get_public_streams(request, user_profile):
    return get_public_streams_backend(request, user_profile)

@authenticated_json_post_view
def json_get_public_streams(request, user_profile):
    return get_public_streams_backend(request, user_profile)

def get_public_streams_backend(request, user_profile):
    if user_profile.realm.domain == "mit.edu" and not is_super_user_api(request):
        return json_error("User not authorized for this query")

    # Only get streams someone is currently subscribed to
    subs_filter = Subscription.objects.filter(active=True).values('recipient_id')
    stream_ids = Recipient.objects.filter(
        type=Recipient.STREAM, id__in=subs_filter).values('type_id')
    streams = sorted(stream.name for stream in
                     Stream.objects.filter(id__in = stream_ids,
                                           realm=user_profile.realm,
                                           invite_only=False))
    return json_success({"streams": streams})

@authenticated_api_view
def api_list_subscriptions(request, user_profile):
    return list_subscriptions_backend(request, user_profile)

@authenticated_json_post_view
def json_list_subscriptions(request, user_profile):
    return list_subscriptions_backend(request, user_profile)

def list_subscriptions_backend(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)})

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
        json_dict.update(simplejson.loads(response.content))
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

    streams = list_to_streams(streams_raw, user_profile)

    result = dict(removed=[], not_subscribed=[])
    for stream in streams:
        did_remove = do_remove_subscription(user_profile, stream)
        if did_remove:
            result["removed"].append(stream.name)
        else:
            result["not_subscribed"].append(stream.name)

    return json_success(result)

@authenticated_api_view
def api_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

@authenticated_json_post_view
def json_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = REQ('subscriptions', json_to_list),
                              invite_only = REQ('invite_only', json_to_bool, default=False),
                              principals = REQ('principals', json_to_list, default=None),):

    stream_names = []
    for stream_name in streams_raw:
        stream_name = stream_name.strip()
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name (%s)." % (stream_name,))
        stream_names.append(stream_name)

    if principals is not None:
        subscribers = set(principal_to_user_profile(user_profile, principal) for principal in principals)
    else:
        subscribers = [user_profile]

    streams = list_to_streams(streams_raw, user_profile, autocreate=True, invite_only=invite_only)
    private_streams = {}
    result = dict(subscribed=[], already_subscribed=[])

    result = dict(subscribed=defaultdict(list), already_subscribed=defaultdict(list))
    for stream in streams:
        (subscribed, already_subscribed) = bulk_add_subscriptions(stream, subscribers)
        for subscriber in subscribed:
            result["subscribed"][subscriber.email].append(stream.name)
        for subscriber in already_subscribed:
            result["already_subscribed"][subscriber.email].append(stream.name)
        private_streams[stream.name] = stream.invite_only

    # Inform the user if someone else subscribed them to stuff
    if principals and result["subscribed"]:
        for email, subscriptions in result["subscribed"].iteritems():
            if email == user_profile.email:
                # Don't send a Humbug if you invited yourself.
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
            msg += "\nYou can see historical content on a non-invite-only stream by narrowing to it."
            internal_send_message("humbug+notifications@humbughq.com",
                                  "private", email, "", msg)

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])
    return json_success(result)

@authenticated_api_view
def api_get_members(request, user_profile):
    return get_members_backend(request, user_profile)

@authenticated_json_post_view
def json_get_members(request, user_profile):
    return get_members_backend(request, user_profile)

def get_members_backend(request, user_profile):
    members = [(profile.full_name, profile.email) for profile in \
                   UserProfile.objects.select_related().filter(realm=user_profile.realm)]
    return json_success({'members': members})

@authenticated_api_view
def api_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

@authenticated_json_post_view
def json_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

def gen_s3_key(user_profile, name):
    split_name = name.split('.')
    base = ".".join(split_name[:-1])
    extension = split_name[-1]

    # To come up with a s3 key we randomly generate a "directory". The "file
    # name" is the original filename provided by the user run through Django's
    # slugify.

    return base64.urlsafe_b64encode(os.urandom(60)) + "/" + slugify(base) + "." + slugify(extension)

@authenticated_json_post_view
def json_upload_file(request, user_profile):
    if len(request.FILES) == 0:
        return json_error("You must specify a file to upload")
    if len(request.FILES) != 1:
        return json_error("You may only upload one file at a time")

    user_file = request.FILES.values()[0]
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    key = Key(conn.get_bucket(settings.S3_BUCKET))

    uploaded_file_name = user_file.name
    content_type = request.GET.get('mimetype')
    if content_type is None:
        content_type = guess_type(uploaded_file_name)[0]
    else:
        uploaded_file_name = uploaded_file_name + guess_extension(content_type)

    key.key = gen_s3_key(user_profile, uploaded_file_name)

    # So for writing the file to S3, the file could either be stored in RAM
    # (if it is less than 2.5MiB or so) or an actual temporary file on disk.
    #
    # Because we set FILE_UPLOAD_MAX_MEMORY_SIZE to 0, only the latter case
    # should occur in practice.
    #
    # This is great, because passing the pseudofile object that Django gives
    # you to boto would be a pain.

    key.set_metadata("user_profile_id", str(user_profile.id))
    if content_type:
        headers = {'Content-Type': content_type}
    else:
        headers = None
    key.set_contents_from_filename(
            user_file.temporary_file_path(),
            headers=headers)
    return json_success({'uri': "https://%s.s3.amazonaws.com/%s" % (settings.S3_BUCKET, key.key)})

@has_request_variables
def get_subscribers_backend(request, user_profile, stream_name=REQ('stream')):
    if user_profile.realm.domain == "mit.edu":
        return json_error("You cannot get subscribers in this realm")

    stream = get_stream(stream_name, user_profile.realm)
    if stream is None:
        return json_error("Stream does not exist: %s" % stream_name)

    if stream.invite_only and not subscribed_to_stream(user_profile, stream):
        return json_error("Unable to retrieve subscribers for invite-only stream")

    subscriptions = Subscription.objects.filter(recipient__type=Recipient.STREAM,
                                                recipient__type_id=stream.id,
                                                active=True).select_related()

    return json_success({'subscribers': [subscription.user_profile.email
                                         for subscription in subscriptions]})

@authenticated_json_post_view
@has_request_variables
def json_change_settings(request, user_profile, full_name=REQ,
                         old_password=REQ, new_password=REQ,
                         confirm_password=REQ,
                         # enable_desktop_notification needs to default to False
                         # because browsers POST nothing for an unchecked checkbox
                         enable_desktop_notifications=REQ(converter=lambda x: x == "on",
                                                          default=False),
                         enable_sounds=REQ(converter=lambda x: x == "on",
                                                          default=False),
                         enable_offline_email_notifications=REQ(converter=lambda x: x == "on",
                                                                default=False)):
    if new_password != "" or confirm_password != "":
        if new_password != confirm_password:
            return json_error("New password must match confirmation password!")
        if not authenticate(username=user_profile.email, password=old_password):
            return json_error("Wrong password!")
        do_change_password(user_profile, new_password)

    result = {}
    if user_profile.full_name != full_name and full_name.strip() != "":
        do_change_full_name(user_profile, full_name.strip())
        result['full_name'] = full_name

    if user_profile.enable_desktop_notifications != enable_desktop_notifications:
        do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications)
        result['enable_desktop_notifications'] = enable_desktop_notifications

    if user_profile.enable_sounds != enable_sounds:
        do_change_enable_sounds(user_profile, enable_sounds)
        result['enable_sounds'] = enable_sounds

    if user_profile.enable_offline_email_notifications != enable_offline_email_notifications:
        do_change_enable_offline_email_notifications(user_profile, enable_offline_email_notifications)
        result['enable_offline_email_notifications'] = enable_offline_email_notifications

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
            setattr(sub, property, value)
            sub.save(update_fields=[property])
            log_subscription_property_change(user_profile.email, stream_name,
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
    def __init__(self, client_name, queries, default_tab=False):
        self.default_tab = default_tab
        self.has_pointer = False
        self.rows = {}

        def do_url(query_name, url):
            for record in UserActivity.objects.filter(
                    query=url,
                    client__name__startswith=client_name).select_related():
                row = self.rows.setdefault(record.user_profile.email,
                                           {'realm': record.user_profile.realm.domain,
                                            'full_name': record.user_profile.full_name,
                                            'email': record.user_profile.email})
                row[query_name + '_count'] = record.count
                row[query_name + '_last' ] = record.last_visit

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
        return sorted(self.rows.iteritems(), key=lambda (k,r): r['age'])

def can_view_activity(request):
    return request.user.realm.domain == 'humbughq.com'

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def get_activity(request):
    if not can_view_activity(request):
        return HttpResponseRedirect(reverse('zephyr.views.login_page'))

    web_queries = (
        ("get_updates",    ["/json/get_updates", "/json/get_events"]),
        ("send_message",   ["/json/send_message"]),
        ("update_pointer", ["/json/update_pointer"]),
    )

    api_queries = (
        ("get_updates",  ["/api/v1/get_messages", "/api/v1/messages/latest", "/api/v1/events"]),
        ("send_message", ["/api/v1/send_message"]),
    )

    return render_to_response('zephyr/activity.html',
        { 'data': {
            'Website': ActivityTable('website',       web_queries, default_tab=True),
            'Mirror':  ActivityTable('zephyr_mirror', api_queries),
            'API':     ActivityTable('API',           api_queries),
            'Android': ActivityTable('Android',       api_queries),
            'iPhone':  ActivityTable('iPhone',        api_queries)
        }}, context_instance=RequestContext(request))

def build_message_from_gitlog(user_profile, name, ref, commits, before, after, url, pusher):
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = name

    if re.match(r'^0+$', after):
        content = "%s deleted branch %s" % (pusher,
                                            short_ref)
    elif len(commits) == 0:
        content = ("%s [force pushed](%s) to branch %s.  Head is now %s"
                   % (pusher,
                      url,
                      short_ref,
                      after[:7]))
    else:
        content = ("%s [pushed](%s) to branch %s\n\n"
                   % (pusher,
                      url,
                      short_ref))
        num_commits = len(commits)
        max_commits = 10
        truncated_commits = commits[:max_commits]
        for commit in truncated_commits:
            short_id = commit['id'][:7]
            (short_commit_msg, _, _) = commit['message'].partition("\n")
            content += "* [%s](%s): %s\n" % (short_id, commit['url'],
                                             short_commit_msg)
        if (num_commits > max_commits):
            content += ("\n[and %d more commits]"
                        % (num_commits - max_commits,))

    return (subject, content)

@authenticated_api_view
@has_request_variables
def api_github_landing(request, user_profile, event=REQ,
                       payload=REQ(converter=json_to_dict),
                       branches=REQ(default=''),
                       stream=REQ(default='')):
    # TODO: this should all be moved to an external bot
    repository = payload['repository']

    if not stream:
        stream = 'commits'

    # CUSTOMER18 has requested not to get pull request notifications
    if event == 'pull_request' and user_profile.realm.domain not in ['customer18.invalid', 'humbughq.com']:
        pull_req = payload['pull_request']

        subject = "%s: pull request %d" % (repository['name'],
                                           pull_req['number'])
        content = ("Pull request from %s [%s](%s):\n\n %s\n\n> %s"
                   % (pull_req['user']['login'],
                      payload['action'],
                      pull_req['html_url'],
                      pull_req['title'],
                      pull_req['body']))
    elif event == 'push':
        short_ref = re.sub(r'^refs/heads/', '', payload['ref'])
        # This is a bit hackish, but is basically so that CUSTOMER18 doesn't
        # get spammed when people commit to non-master all over the place.
        # Long-term, this will be replaced by some GitHub configuration
        # option of which branches to notify on.
        if short_ref != 'master' and user_profile.realm.domain in ['customer18.invalid', 'humbughq.com']:
            return json_success()

        if branches:
            # If we are given a whitelist of branches, then we silently ignore
            # any push notification on a branch that is not in our whitelist.
            if short_ref not in re.split('[\s,;|]+', branches):
                return json_success()


        subject, content = build_message_from_gitlog(user_profile, repository['name'],
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['compare'],
                                                     payload['pusher']['name'])
    else:
        # We don't handle other events even though we get notified
        # about them
        return json_success()

    subject = elide_subject(subject)

    request.client = get_client("github_bot")
    return send_message_backend(request, user_profile,
                                message_type_name="stream",
                                message_to=[stream],
                                forged=False, subject_name=subject,
                                message_content=content)

def elide_subject(subject):
    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[:57].rstrip() + '...'
    return subject

@csrf_exempt
def api_jira_webhook(request):
    try:
        api_key = request.GET['api_key']
    except (AttributeError, KeyError):
        return json_error("Missing api_key parameter.")

    try:
        payload = simplejson.loads(request.body)
    except simplejson.JSONDecodeError:
        return json_error("Malformed JSON input")

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'jira'

    try:
        user_profile = UserProfile.objects.get(api_key=api_key)
    except UserProfile.DoesNotExist:
        return json_error("Failed to find user with API key: %s" % (api_key,))

    def get_in(payload, keys, default=''):
        try:
            for key in keys:
                payload = payload[key]
        except (AttributeError, KeyError):
            return default
        return payload

    event = payload.get('webhookEvent')
    author = get_in(payload, ['user', 'displayName'])
    issueId = get_in(payload, ['issue', 'key'])
    # Guess the URL as it is not specified in the payload
    # We assume that there is a /browse/BUG-### page
    # from the REST url of the issue itself
    baseUrl = re.match("(.*)\/rest\/api/.*", get_in(payload, ['issue', 'self']))
    if baseUrl and len(baseUrl.groups()):
        issue = "[%s](%s/browse/%s)" % (issueId, baseUrl.group(1), issueId)
    else:
        issue = issueId
    title = get_in(payload, ['issue', 'fields', 'summary'])
    priority = get_in(payload, ['issue', 'fields', 'priority', 'name'])
    assignee = get_in(payload, ['assignee', 'displayName'], 'no one')
    subject = "%s: %s" % (issueId, title)

    if event == 'jira:issue_created':
        content = "%s **created** %s priority %s, assigned to **%s**:\n\n> %s" % \
                  (author, issue, priority, assignee, title)
    elif event == 'jira:issue_deleted':
        content = "%s **deleted** %s!" % \
                  (author, issue)
    elif event == 'jira:issue_updated':
        # Reassigned, commented, reopened, and resolved events are all bundled
        # into this one 'updated' event type, so we try to extract the meaningful
        # event that happened
        content = "%s **updated** %s:\n\n" % (author, issue)
        changelog = get_in(payload, ['changelog',])
        comment = get_in(payload, ['comment', 'body'])

        if changelog != '':
            # Use the changelog to display the changes, whitelist types we accept
            items = changelog.get('items')
            for item in items:
                field = item.get('field')
                if field in ('status', 'assignee'):
                    content += "* Changed %s from **%s** to **%s**\n" % (field, item.get('fromString'), item.get('toString'))

        if comment != '':
            content += "\n> %s" % (comment,)
    else:
        # Unknown event type
        logging.warning("Got JIRA event type we don't understand: %s" % (event,))
        return json_error("Unknown JIRA event type")

    subject = elide_subject(subject)

    ret = check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
    if ret is not None:
        return json_error(ret)
    return json_success()

@csrf_exempt
def api_pivotal_webhook(request):
    try:
        api_key = request.GET['api_key']
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing api_key or stream parameter.")

    try:
        user_profile = UserProfile.objects.get(api_key=api_key)
    except UserProfile.DoesNotExist:
        return json_error("Failed to find user with API key: %s" % (api_key,))

    payload = xml_fromstring(request.body)

    def get_text(attrs):
        start = payload
        try:
            for attr in attrs:
                start = start.find(attr)
            return start.text
        except AttributeError:
            return ""

    try:
        event_type = payload.find('event_type').text
        description = payload.find('description').text
        project_id = payload.find('project_id').text
        story_id = get_text(['stories', 'story', 'id'])
        # Ugh, the URL in the XML data is not a clickable url that works for the user
        # so we try to build one that the user can actually click on
        url = "https://www.pivotaltracker.com/s/projects/%s/stories/%s" % (project_id, story_id)

        # Pivotal doesn't tell us the name of the story, but it's usually in the
        # description in quotes as the first quoted string
        name_re = re.compile(r'[^"]+"([^"]+)".*')
        match = name_re.match(description)
        if match and len(match.groups()):
            name = match.group(1)
        else:
            name = "Story changed" # Failed for an unknown reason, show something
        more_info = " [(view)](%s)" % (url,)

        if event_type == 'story_update':
            subject = name
            content = description + more_info
        elif event_type == 'note_create':
            subject = "Comment added"
            content = description +  more_info
        elif event_type == 'story_create':
            issue_desc = get_text(['stories', 'story', 'description'])
            issue_type = get_text(['stories', 'story', 'story_type'])
            issue_status = get_text(['stories', 'story', 'current_state'])
            estimate = get_text(['stories', 'story', 'estimate'])
            if estimate != '':
                estimate = " worth %s story points" % (estimate,)
            subject = name
            content = "%s (%s %s%s):\n\n> %s\n\n%s" % (description,
                                                       issue_status,
                                                       issue_type,
                                                       estimate,
                                                       issue_desc,
                                                       more_info)

    except AttributeError:
        return json_error("Failed to extract data from Pivotal XML response")

    subject = elide_subject(subject)

    ret = check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
    if ret is not None:
        return json_error(ret)
    return json_success()

# Beanstalk's web hook UI rejects url with a @ in the username section of a url
# So we ask the user to replace them with %40
# We manually fix the username here before passing it along to @authenticated_rest_api_view
def beanstalk_decoder(view_func):
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        try:
            auth_type, encoded_value = request.META['HTTP_AUTHORIZATION'].split()
            if auth_type.lower() == "basic":
                email, api_key = base64.b64decode(encoded_value).split(":")
                email = email.replace('%40', '@')
                request.META['HTTP_AUTHORIZATION'] = "Basic %s" % (base64.b64encode("%s:%s" % (email, api_key)))
        except:
            pass

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func

@csrf_exempt
@beanstalk_decoder
@authenticated_rest_api_view
@has_request_variables
def api_beanstalk_webhook(request, user_profile,
                          payload=REQ(converter=json_to_dict)):
    # Beanstalk supports both SVN and git repositories
    # We distinguish between the two by checking for a
    # 'uri' key that is only present for git repos
    git_repo = 'uri' in payload
    if git_repo:
        # To get a linkable url,
        subject, content = build_message_from_gitlog(user_profile, payload['repository']['name'],
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['repository']['url'],
                                                     payload['pusher_name'])
    else:
        author = payload.get('author_full_name')
        url = payload.get('changeset_url')
        revision = payload.get('revision')
        (short_commit_msg, _, _) = payload.get('message').partition("\n")

        subject = "svn r%s" % (revision,)
        content = "%s pushed [revision %s](%s):\n\n> %s" % (author, revision, url, short_commit_msg)

    subject = elide_subject(subject)

    ret = check_send_message(user_profile, get_client("API"), "stream", ["commits"], subject, content)
    if ret is not None:
        return json_error(ret)
    return json_success()

def get_status_list(requesting_user_profile):
    return {'presences': get_status_dict(requesting_user_profile),
            'server_timestamp': time.time()}

@authenticated_json_post_view
@has_request_variables
def json_update_active_status(request, user_profile, status=REQ):
    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError("Invalid presence status: %s" % (status,))
    else:
        update_user_presence(user_profile, request.client, now(), status_val)

    ret = get_status_list(user_profile)
    if user_profile.realm.domain == "mit.edu":
        try:
            # We renamed /api/v1/get_messages to /api/v1/events
            try:
                activity = UserActivity.objects.get(user_profile = user_profile,
                                                    query="/api/v1/events",
                                                    client__name="zephyr_mirror")
            except UserActivity.DoesNotExist:
                activity = UserActivity.objects.get(user_profile = user_profile,
                                                    query="/api/v1/get_messages",
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
    js_source_map = SourceMap(path.join(
        settings.SITE_ROOT, '../prod-static/source-map/app.js.map'))

@authenticated_json_post_view
@has_request_variables
def json_report_error(request, user_profile, message=REQ, stacktrace=REQ,
                      ui_message=REQ(converter=json_to_bool), user_agent=REQ,
                      href=REQ,
                      more_info=REQ(converter=json_to_dict, default=None)):
    subject = "error for %s" % (user_profile.email,)
    if ui_message:
        subject = "User-visible browser " + subject
    else:
        subject = "Browser " + subject

    if js_source_map:
        stacktrace = js_source_map.annotate_stacktrace(stacktrace)

    body = ("Message:\n%s\n\nStacktrace:\n%s\n\nUser agent: %s\nhref: %s\n"
            "User saw error in UI: %s"
            % (message, stacktrace, user_agent, href, ui_message))

    if more_info is not None:
        body += "\n\nAdditional information:"
        for (key, value) in more_info.iteritems():
            body += "\n  %s: %s" % (key, value)

    mail_admins(subject, body)
    return json_success()

@authenticated_json_post_view
def json_events_register(request, user_profile):
    return events_register_backend(request, user_profile)

# Does not need to be authenticated because it's called from rest_dispatch
@has_request_variables
def api_events_register(request, user_profile,
                        apply_markdown=REQ(default=False, converter=json_to_bool)):
    return events_register_backend(request, user_profile,
                                   apply_markdown=apply_markdown)

@has_request_variables
def events_register_backend(request, user_profile, apply_markdown=True,
                            event_types=REQ(converter=json_to_list, default=None)):
    ret = do_events_register(user_profile, request.client, apply_markdown,
                             event_types)
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

    bot_profile = do_create_user(email, '', user_profile.realm, full_name,
                                 short_name, True, True, user_profile)
    return json_success({'api_key': bot_profile.api_key})

@authenticated_json_post_view
def json_get_bots(request, user_profile):
    bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                              bot_owner=user_profile)
    return json_success({'bots': [{'username': bp.email, 'full_name': bp.full_name,
                                   'api_key': bp.api_key}
                                  for bp in bot_profiles]})
