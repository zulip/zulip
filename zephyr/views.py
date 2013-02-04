from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext, loader
from django.utils.timezone import utc, now
from django.core.exceptions import ValidationError
from django.core import validators
from django.contrib.auth.views import login as django_login_page
from django.db.models import Q
from django.core.mail import send_mail
from zephyr.models import Message, UserProfile, Stream, Subscription, \
    Recipient, get_display_recipient, get_huddle, Realm, UserMessage, \
    StreamColor, PreregistrationUser, get_client, MitUser, User, UserActivity, \
    MAX_SUBJECT_LENGTH, MAX_MESSAGE_LENGTH, get_stream
from zephyr.lib.actions import do_add_subscription, do_remove_subscription, \
    do_change_password, create_mit_user_if_needed, \
    do_change_full_name, do_change_enable_desktop_notifications, \
    do_activate_user, add_default_subs, do_create_user, do_send_message, \
    log_subscription_property_change, internal_send_message, \
    create_stream_if_needed, gather_subscriptions, subscribed_to_stream
from zephyr.forms import RegistrationForm, HomepageForm, ToSForm, is_unique, \
    is_active, isnt_mit
from django.views.decorators.csrf import csrf_exempt, requires_csrf_token

from zephyr.decorator import require_post, \
    authenticated_api_view, authenticated_json_post_view, \
    has_request_variables, POST, authenticated_json_view, \
    to_non_negative_int, json_to_dict, json_to_list, json_to_bool, \
    JsonableError
from zephyr.lib.query import last_n
from zephyr.lib.avatar import gravatar_hash
from zephyr.lib.response import json_success, json_error
from zephyr.lib.timestamp import timestamp_to_datetime

from confirmation.models import Confirmation

import datetime
import simplejson
import re
import urllib
import time
import requests
import os
import base64
from collections import defaultdict

SERVER_GENERATION = int(time.time())

def send_signup_message(sender, signups_stream, user_profile, internal=False):
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    internal_send_message(sender,
            Recipient.STREAM, signups_stream, user_profile.realm.domain,
            "%s <`%s`> just signed up for Humbug!%s(total: **%i**)" % (
                user_profile.full_name,
                user_profile.user.email,
                internal_blurb,
                UserProfile.objects.filter(realm=user_profile.realm,
                                           user__is_active=True).count(),
                )
            )

def notify_new_user(user_profile, internal=False):
    send_signup_message("humbug+signups@humbughq.com", "signups", user_profile, internal)

    if user_profile.realm.domain == "customer29.invalid":
        try:
            send_signup_message("bot1@customer29.invalid", "signups", user_profile, internal)
        except UserProfile.DoesNotExist:
            pass

class PrincipalError(JsonableError):
    def __init__(self, principal):
        self.principal = principal

    def to_json_error_msg(self):
        return ("User not authorized to execute queries on behalf of '%s'"
                % (self.principal,))

def principal_to_user_profile(agent, principal):
    principal_doesnt_exist = False
    try:
        principal_user_profile = UserProfile.objects.get(user__email=principal)
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

# This view is both CSRF exempt and requires the token. This is because
# depending on whether the user arrived here via a redirect from Thymes
# or is submitting the form we either want to validate CSRF or not.
#
# See also:
# <https://docs.djangoproject.com/en/dev/ref/contrib/csrf/#view-needs-protection-for-one-path>
@require_post
@csrf_exempt
@requires_csrf_token
def accounts_customer30(request):
    domain = 'customer30.invalid'

    # support a username, realname via either GET or POST
    try:
        username = request.POST['username']
        realname = request.POST['realname']
    except KeyError:
        return HttpResponseBadRequest('You must POST with username and realname parameters.')

    if not username.isalnum():
        return HttpResponseBadRequest("Your username was non-alphanumeric and is not allowed.")
    email = username + '@' + domain
    try:
        is_unique(email)
    except ValidationError:
        return HttpResponseBadRequest("That username is already registered with Humbug.")

    try:
        request.POST['terms']
    except KeyError:
        return render_to_response('zephyr/accounts_customer30.html',
                {'username': username,
                 'realname': realname,
                 'company_name': domain},
                context_instance=RequestContext(request))

    # We want CSRF protection if you're actually registering, not if you're just displaying the form
    return accounts_customer30_register(request, username, realname, email, domain)

def accounts_customer30_register(request, username, realname, email, domain):
    user_profile = do_create_user(email,
                                  "xxxxxxxxxxx",
                                  Realm.objects.get_or_create(domain=domain)[0],
                                  realname,
                                  username)
    add_default_subs(user_profile)
    login(request, authenticate(username=email, password="xxxxxxxxxxx"))
    notify_new_user(user_profile)
    return HttpResponseRedirect(reverse('zephyr.views.home'))

@require_post
def accounts_register(request):
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    mit_beta_user = isinstance(confirmation.content_object, MitUser)

    company_name = email.split('@')[-1]

    try:
        if mit_beta_user:
            # MIT users already exist, but are supposed to be inactive.
            is_active(email)
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
            domain     = email.split('@')[-1]
            (realm, _) = Realm.objects.get_or_create(domain=domain)

            # FIXME: sanitize email addresses and fullname
            if mit_beta_user:
                user = User.objects.get(email=email)
                do_activate_user(user)
                do_change_password(user, password)
                user_profile = user.userprofile
                do_change_full_name(user_profile, full_name)
            else:
                user_profile = do_create_user(email, password, realm, full_name, short_name)
                # We want to add the default subs list iff there were no subs
                # specified when the user was invited.
                streams = prereg_user.streams.all()
                if len(streams) == 0:
                    add_default_subs(user_profile)
                else:
                    for stream in streams:
                        do_add_subscription(user_profile, stream)
                if prereg_user.referred_by is not None:
                    # This is a cross-realm private message.
                    internal_send_message("humbug+signups@humbughq.com",
                            Recipient.PERSONAL, prereg_user.referred_by.user.email, user_profile.realm.domain,
                            "%s <`%s`> accepted your invitation to join Humbug!" % (
                                user_profile.full_name,
                                user_profile.user.email,
                                )
                            )

            notify_new_user(user_profile)

            login(request, authenticate(username=email, password=password))
            return HttpResponseRedirect(reverse('zephyr.views.home'))

    return render_to_response('zephyr/register.html',
        { 'form': form, 'company_name': company_name, 'email': email, 'key': key },
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
            do_change_full_name(request.user.userprofile, full_name)
            return redirect(home)

    else:
        form = ToSForm()
    return render_to_response('zephyr/accounts_accept_terms.html',
        { 'form': form, 'company_name': company_name, 'email': email },
        context_instance=RequestContext(request))

@authenticated_json_post_view
@has_request_variables
def json_invite_users(request, user_profile, invitee_emails=POST):
    # Validation
    if settings.ALLOW_REGISTER == False:
        try:
            isnt_mit(user_profile.user.email)
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
        try:
            validators.validate_email(email)
        except ValidationError:
            errors.append((email, "Invalid address."))
            continue

        if email.split('@')[-1] != user_profile.realm.domain:
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
        user = PreregistrationUser(email=email, referred_by=user_profile)

        # We save twice because you cannot associate a ManyToMany field
        # on an unsaved object.
        user.save()
        user.streams = streams
        user.save()

        new_prereg_users.append(user)

    if errors:
        return json_error(data={'errors': errors},
                          msg="Some emails did not validate. No invites have been sent.")

    # If we encounter an exception at any point before now, there are no unwanted side-effects,
    # since it is totally fine to have duplicate PreregistrationUsers
    for user in new_prereg_users:
        Confirmation.objects.send_confirmation(user, user.email,
                additional_context={'referrer': user_profile},
                subject_template_path='confirmation/invite_email_subject.txt',
                body_template_path='confirmation/invite_email_body.txt')

    return json_success()

def login_page(request, **kwargs):
    template_response = django_login_page(request, **kwargs)
    try:
        template_response.context_data['email'] = request.GET['email']
    except KeyError:
        pass
    return template_response

def accounts_home(request):
    if request.method == 'POST':
        form = HomepageForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = PreregistrationUser()
            user.email = email
            user.save()
            Confirmation.objects.send_confirmation(user, user.email)
            return HttpResponseRedirect(reverse('send_confirm', kwargs={'email':user.email}))
        try:
            email = request.POST['email']
            is_unique(email)
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

    user_profile = UserProfile.objects.get(user=request.user)

    lurk_stream = None
    lurk_name = request.GET.get('lurk')
    if lurk_name is not None:
        try:
            lurk_stream = get_public_stream(request, lurk_name, user_profile.realm)
        except JsonableError:
            # Something bad happened, e.g. nonexistent or non-public stream.
            # Fall back to the regular Home view as though we never existed.
            lurk_name = None

    if lurk_stream is not None:
        recipient = Recipient.objects.get(type_id=lurk_stream.id, type=Recipient.STREAM)
        num_messages = Message.objects.filter(recipient=recipient).count()

        # There are no per-user-and-stream pointers, so let's have the
        # client initially select the most recent message to the
        # stream.
        if num_messages > 0:
            initial_pointer = Message.objects.filter(recipient=recipient).order_by('id').reverse()[0].id
        else:
            initial_pointer = -1
    else:
        num_messages = UserMessage.objects.filter(user_profile=user_profile).count()

        if user_profile.pointer == -1 and num_messages > 0:
            # Put the new user's pointer at the bottom
            #
            # This improves performance, because we limit backfilling of messages
            # before the pointer.  It's also likely that someone joining an
            # organization is interested in recent messages more than the very
            # first messages on the system.

            max_id = (UserMessage.objects.filter(user_profile=user_profile)
                                         .order_by('message')
                                         .reverse()[0]).message_id
            user_profile.pointer = max_id
            user_profile.last_pointer_updater = request.session.session_key

        initial_pointer = user_profile.pointer

    # Populate personals autocomplete list based on everyone in your
    # realm.  Later we might want a 2-layer autocomplete, where we
    # consider specially some sort of "buddy list" who e.g. you've
    # talked to before, but for small organizations, the right list is
    # everyone in your realm.
    people = [{'email'     : profile.user.email,
               'full_name' : profile.full_name}
              for profile in
              UserProfile.objects.select_related().filter(realm=user_profile.realm)]

    subscriptions = Subscription.objects.select_related().filter(user_profile_id=user_profile, active=True)
    streams = [get_display_recipient(sub.recipient) for sub in subscriptions
               if sub.recipient.type == Recipient.STREAM]

    desktop_notifications_enabled = (user_profile.enable_desktop_notifications
        and getattr(settings, 'ENABLE_NOTIFICATIONS', True))

    js_bool = lambda x: 'true' if x else 'false'

    try:
        isnt_mit(user_profile.user.email)
        show_invites = True
    except ValidationError:
        show_invites = settings.ALLOW_REGISTER

    return render_to_response('zephyr/index.html',
                              {'user_profile': user_profile,
                               'email_hash'  : gravatar_hash(user_profile.user.email),
                               'people'      : people,
                               'streams'     : streams,
                               'poll_timeout': settings.POLL_TIMEOUT,
                               'initial_pointer':
                                   initial_pointer,
                               'have_initial_messages':
                                   js_bool(num_messages > 0),
                               'desktop_notifications_enabled':
                                   js_bool(desktop_notifications_enabled),
                               'show_debug':
                                   settings.DEBUG and ('show_debug' in request.GET),
                               'show_activity': can_view_activity(request),
                               'show_invites': show_invites,
                               'lurk_stream': lurk_name
                               },
                              context_instance=RequestContext(request))

@authenticated_api_view
@has_request_variables
def api_update_pointer(request, user_profile, updater=POST('client_id')):
    return update_pointer_backend(request, user_profile, updater)

@authenticated_json_post_view
def json_update_pointer(request, user_profile):
    return update_pointer_backend(request, user_profile,
                                  request.session.session_key)

@has_request_variables
def update_pointer_backend(request, user_profile, updater,
                           pointer=POST(converter=to_non_negative_int)):
    if pointer <= user_profile.pointer:
        return json_success()

    user_profile.pointer = pointer
    user_profile.last_pointer_updater = updater
    user_profile.save()

    if settings.TORNADO_SERVER:
        requests.post(settings.TORNADO_SERVER + '/notify_pointer_update', data=dict(
            secret          = settings.SHARED_SECRET,
            user            = user_profile.id,
            new_pointer     = pointer,
            pointer_updater = updater))

    return json_success()

@authenticated_json_post_view
def json_get_old_messages(request, user_profile):
    return get_old_messages_backend(request, user_profile=user_profile,
                                    apply_markdown=True)

@authenticated_api_view
@has_request_variables
def api_get_old_messages(request, user_profile,
                         apply_markdown=POST(default=False,
                                             converter=simplejson.loads)):
    return get_old_messages_backend(request, user_profile=user_profile,
                                    apply_markdown=apply_markdown)

class BadNarrowOperator(Exception):
    def __init__(self, desc):
        self.desc = desc

    def to_json_error_msg(self):
        return 'Invalid narrow operator: ' + self.desc

class NarrowBuilder(object):
    def __init__(self, user_profile):
        self.user_profile = user_profile

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

    def by_is(self, operand):
        if operand == 'private-message':
            return (Q(recipient__type=Recipient.PERSONAL) |
                    Q(recipient__type=Recipient.HUDDLE))
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    def by_stream(self, operand):
        stream = get_stream(operand, self.user_profile.realm)
        if stream is None:
            raise BadNarrowOperator('unknown stream ' + operand)
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
        return Q(recipient=recipient)

    def by_subject(self, operand):
        return Q(subject=operand)

    def by_pm_with(self, operand):
        if ',' in operand:
            # Huddle
            try:
                emails = [e.strip() for e in operand.split(',')]
                recipient = recipient_for_emails(emails, False,
                    self.user_profile, self.user_profile)
            except ValidationError:
                raise BadNarrowOperator('unknown recipient ' + operand)
            return Q(recipient=recipient)
        else:
            # Personal message
            self_recipient = Recipient.objects.get(type=Recipient.PERSONAL,
                                                   type_id=self.user_profile.id)
            if operand == self.user_profile.user.email:
                # Personals with self
                return Q(recipient__type=Recipient.PERSONAL,
                         sender=self.user_profile, recipient=self_recipient)

            # Personals with other user; include both directions.
            try:
                narrow_profile = UserProfile.objects.get(user__email=operand)
            except UserProfile.DoesNotExist:
                raise BadNarrowOperator('unknown user ' + operand)

            narrow_recipient = Recipient.objects.get(type=Recipient.PERSONAL,
                                                     type_id=narrow_profile.id)
            return ((Q(sender=narrow_profile) & Q(recipient=self_recipient)) |
                    (Q(sender=self.user_profile) & Q(recipient=narrow_recipient)))

    def do_search(self, query, operand):
        words = operand.split()
        if "postgres" in settings.DATABASES["default"]["ENGINE"]:
            sql = "to_tsvector('english', subject || ' ' || content) @@ to_tsquery('english', %s)"
            return query.extra(where=[sql], params=[" & ".join(words)])
        else:
            for word in words:
                query = query.filter(Q(content__icontains=word) |
                                     Q(subject__icontains=word))
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

def get_public_stream(request, stream, realm):
    if not valid_stream_name(stream):
        raise JsonableError("Invalid stream name")
    stream = get_stream(stream, realm)
    if stream is None:
        raise JsonableError("Stream does not exist")
    if not stream.is_public():
        raise JsonableError("Stream is not public")
    return stream

@has_request_variables
def get_old_messages_backend(request, anchor = POST(converter=to_non_negative_int),
                             num_before = POST(converter=to_non_negative_int),
                             num_after = POST(converter=to_non_negative_int),
                             narrow = POST('narrow', converter=narrow_parameter, default=None),
                             stream = POST(default=None),
                             user_profile=None, apply_markdown=True):
    if stream is not None:
        stream = get_public_stream(request, stream, user_profile.realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        query = Message.objects.select_related().filter(recipient = recipient).order_by('id')
    else:
        query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')

    if narrow is not None:
        build = NarrowBuilder(user_profile)
        for operator, operand in narrow:
            query = build(query, operator, operand)

    # We add 1 to the number of messages requested to ensure that the
    # resulting list always contains the anchor message
    if num_before != 0 and num_after == 0:
        num_before += 1
        messages = last_n(num_before, query.filter(id__lte=anchor))
    elif num_before == 0 and num_after != 0:
        num_after += 1
        messages = query.filter(id__gte=anchor)[:num_after]
    else:
        num_after += 1
        messages = (last_n(num_before, query.filter(id__lt=anchor))
                    + list(query.filter(id__gte=anchor)[:num_after]))

    ret = {'messages': [message.to_dict(apply_markdown) for message in messages],
           "result": "success",
           "msg": ""}
    return json_success(ret)

def generate_client_id():
    return base64.b16encode(os.urandom(16)).lower()

@authenticated_api_view
def api_get_profile(request, user_profile):
    result = dict(pointer        = user_profile.pointer,
                  client_id      = generate_client_id(),
                  max_message_id = -1)

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

@authenticated_api_view
def api_send_message(request, user_profile):
    return send_message_backend(request, user_profile, request._client)

@authenticated_json_post_view
def json_send_message(request, user_profile):
    return send_message_backend(request, user_profile, request._client)

# Currently tabbott/extra@mit.edu is our only superuser.  TODO: Make
# this a real superuser security check.
def is_super_user_api(request):
    return request.POST.get("api-key") in ["xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"]

def already_sent_mirrored_message(message):
    if message.recipient.type == Recipient.HUDDLE:
        # For huddle messages, we use a 10-second window because the
        # timestamps aren't guaranteed to actually match between two
        # copies of the same message.
        time_window = datetime.timedelta(seconds=10)
    else:
        time_window = datetime.timedelta(seconds=0)

    # Since our database doesn't store timestamps with
    # better-than-second resolution, we should do our comparisons
    # using objects at second resolution
    pub_date_lowres = message.pub_date.replace(microsecond=0)
    return Message.objects.filter(
        sender=message.sender,
        recipient=message.recipient,
        content=message.content,
        subject=message.subject,
        sending_client=message.sending_client,
        pub_date__gte=pub_date_lowres - time_window,
        pub_date__lte=pub_date_lowres + time_window).exists()

# Validte that the passed in object is an email address from the user's realm
# TODO: Check that it's a real email address here.
def same_realm_email(user_profile, email):
    try:
        domain = email.split("@", 1)[1]
        return user_profile.realm.domain == domain
    except:
        return False

def extract_recipients(raw_recipients):
    try:
        recipients = json_to_list(raw_recipients)
    except simplejson.decoder.JSONDecodeError:
        recipients = [raw_recipients]

    # Strip recipients, and then remove any duplicates and any that
    # are the empty string after being stripped.
    recipients = [recipient.strip() for recipient in recipients]
    return list(set(recipient for recipient in recipients if recipient))

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
        if not same_realm_email(user_profile, email):
            return (False, None)

    # Create users for the referenced users, if needed.
    for email in referenced_users:
        create_mit_user_if_needed(user_profile.realm, email)

    sender = UserProfile.objects.get(user__email=sender_email)
    return (True, sender)

def recipient_for_emails(emails, not_forged_zephyr_mirror, user_profile, sender):
    recipient_profile_ids = set()
    for email in emails:
        try:
            recipient_profile_ids.add(UserProfile.objects.get(user__email__iexact=email).id)
        except UserProfile.DoesNotExist:
            raise ValidationError("Invalid email '%s'" % (email,))

    if not_forged_zephyr_mirror and user_profile.id not in recipient_profile_ids:
        raise ValidationError("User not authorized for this query")

    # If the private message is just between the sender and
    # another person, force it to be a personal internally
    if (len(recipient_profile_ids) == 2
        and sender.id in recipient_profile_ids):
        recipient_profile_ids.remove(sender.id)

    if len(recipient_profile_ids) > 1:
        # Make sure the sender is included in huddle messages
        recipient_profile_ids.add(sender.id)
        huddle = get_huddle(list(recipient_profile_ids))
        return Recipient.objects.get(type_id=huddle.id, type=Recipient.HUDDLE)
    else:
        return Recipient.objects.get(type_id=list(recipient_profile_ids)[0],
                                     type=Recipient.PERSONAL)

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
@has_request_variables
def send_message_backend(request, user_profile, client,
                         message_type_name = POST('type'),
                         message_to = POST('to', converter=extract_recipients),
                         forged = POST(default=False),
                         subject_name = POST('subject', lambda x: x.strip(), None),
                         message_content = POST('content')):
    is_super_user = is_super_user_api(request)
    if forged and not is_super_user:
        return json_error("User not authorized for this query")

    if len(message_to) == 0:
        return json_error("Message must have recipients.")
    if len(message_content) > MAX_MESSAGE_LENGTH:
        return json_error("Message too long.")

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

    if message_type_name == 'stream':
        if subject_name is None:
            return json_error("Missing subject")
        if len(message_to) > 1:
            return json_error("Cannot send to multiple streams")
        stream_name = message_to[0].strip()
        if stream_name == "":
            return json_error("Stream can't be empty")
        if subject_name == "":
            return json_error("Subject can't be empty")
        if len(stream_name) > 30:
            return json_error("Stream name too long")
        if len(subject_name) > MAX_SUBJECT_LENGTH:
            return json_error("Subject too long")

        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name")
        ## FIXME: Commented out temporarily while we figure out what we want
        # if not valid_stream_name(subject_name):
        #     return json_error("Invalid subject name")

        stream = get_stream(stream_name, user_profile.realm)
        if stream is None:
            return json_error("Stream does not exist")
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    elif message_type_name == 'private':
        not_forged_zephyr_mirror = client and client.name == "zephyr_mirror" and not forged
        try:
            recipient = recipient_for_emails(message_to, not_forged_zephyr_mirror, user_profile, sender)
        except ValidationError, e:
            return json_error(e.messages[0])
    else:
        return json_error("Invalid message type")

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    if message_type_name == 'stream':
        message.subject = subject_name
    if forged:
        # Forged messages come with a timestamp
        message.pub_date = timestamp_to_datetime(request.POST['time'])
    else:
        message.pub_date = now()
    message.sending_client = client

    if client.name == "zephyr_mirror" and already_sent_mirrored_message(message):
        return json_success()

    do_send_message(message)

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

def get_stream_color(sub):
    try:
        return StreamColor.objects.get(subscription=sub).color
    except StreamColor.DoesNotExist:
        return StreamColor.DEFAULT_STREAM_COLOR

@authenticated_api_view
def api_list_subscriptions(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)})

@authenticated_json_post_view
def json_list_subscriptions(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)})

@authenticated_api_view
def api_remove_subscriptions(request, user_profile):
    return remove_subscriptions_backend(request, user_profile)

@authenticated_json_post_view
def json_remove_subscriptions(request, user_profile):
    return remove_subscriptions_backend(request, user_profile)

@has_request_variables
def remove_subscriptions_backend(request, user_profile,
                                 streams_raw = POST("subscriptions", json_to_list)):
    streams = []
    for stream_name in set(stream_name.strip() for stream_name in streams_raw):
        stream = get_stream(stream_name, user_profile.realm)
        if stream is None:
            return json_error("Stream %s does not exist" % stream_name)
        streams.append(stream)

    result = dict(removed=[], not_subscribed=[])
    for stream in streams:
        did_remove = do_remove_subscription(user_profile, stream)
        if did_remove:
            result["removed"].append(stream.name)
        else:
            result["not_subscribed"].append(stream.name)

    return json_success(result)

def valid_stream_name(name):
    return name != ""

@authenticated_api_view
def api_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

@authenticated_json_post_view
def json_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = POST('subscriptions', json_to_list),
                              invite_only = POST('invite_only', json_to_bool, default=False),
                              principals = POST('principals', json_to_list, default=None),):

    stream_names = []
    for stream_name in streams_raw:
        stream_name = stream_name.strip()
        if len(stream_name) > 30:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name (%s)." % (stream_name,))
        stream_names.append(stream_name)

    if principals is not None:
        subscribers = set(principal_to_user_profile(user_profile, principal) for principal in principals)
    else:
        subscribers = [user_profile]

    private_streams = {}
    result = dict(subscribed=defaultdict(list), already_subscribed=defaultdict(list))
    for stream_name in set(stream_names):
        stream, created = create_stream_if_needed(user_profile.realm, stream_name, invite_only = invite_only)
        # Users cannot subscribe themselves or other people to an invite-only
        # stream they're not on.
        if stream.invite_only and not created and not subscribed_to_stream(user_profile, stream):
            return json_error("Unable to join an invite-only stream")

        for subscriber in subscribers:
            did_subscribe = do_add_subscription(subscriber, stream)
            if did_subscribe:
                result["subscribed"][subscriber.user.email].append(stream.name)
            else:
                result["already_subscribed"][subscriber.user.email].append(stream.name)

        private_streams[stream.name] = stream.invite_only

    # Inform the user if someone else subscribed them to stuff
    if principals and result["subscribed"]:
        for email, subscriptions in result["subscribed"].iteritems():
            if email == user_profile.user.email:
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
            internal_send_message("humbug+notifications@humbughq.com",
                                  Recipient.PERSONAL, email, "", msg)

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])
    return json_success(result)

@authenticated_api_view
def api_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

@authenticated_json_post_view
def json_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

@has_request_variables
def get_subscribers_backend(request, user_profile, stream_name=POST('stream')):
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

    return json_success({'subscribers': [subscription.user_profile.user.email
                                         for subscription in subscriptions]})

@authenticated_json_post_view
@has_request_variables
def json_change_settings(request, user_profile, full_name=POST,
                         old_password=POST, new_password=POST,
                         confirm_password=POST,
                         # enable_desktop_notification needs to default to False
                         # because browsers POST nothing for an unchecked checkbox
                         enable_desktop_notifications=POST(converter=lambda x: x == "on",
                                                           default=False)):
    if new_password != "" or confirm_password != "":
        if new_password != confirm_password:
            return json_error("New password must match confirmation password!")
        if not authenticate(username=user_profile.user.email, password=old_password):
            return json_error("Wrong password!")
        do_change_password(user_profile.user, new_password)

    result = {}
    if user_profile.full_name != full_name and full_name.strip() != "":
        do_change_full_name(user_profile, full_name.strip())
        result['full_name'] = full_name

    if user_profile.enable_desktop_notifications != enable_desktop_notifications:
        do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications)
        result['enable_desktop_notifications'] = enable_desktop_notifications

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_stream_exists(request, user_profile, stream=POST):
    if not valid_stream_name(stream):
        return json_error("Invalid characters in stream name")
    stream = get_stream(stream, user_profile.realm)
    result = {"exists": bool(stream)}
    if stream is not None:
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        result["subscribed"] = Subscription.objects.filter(user_profile=user_profile,
                                                           recipient=recipient,
                                                           active=True).exists()
    return json_success(result)

def set_stream_color(user_profile, stream_name, color):
    stream = get_stream(stream_name, user_profile.realm)
    if not stream:
        return json_error("Invalid stream %s" % (stream.name,))
    recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    subscription = Subscription.objects.filter(user_profile=user_profile,
                                               recipient=recipient, active=True)
    if not subscription.exists():
        return json_error("Not subscribed to stream %s" % (stream_name,))

    stream_color, _ = StreamColor.objects.get_or_create(subscription=subscription[0])
    # TODO: sanitize color.
    stream_color.color = color
    stream_color.save()

class SubscriptionProperties(object):
    """
    A class for managing GET and POST requests for subscription properties. The
    name for a request handler is <request type>_<property name>.

    Requests must have already been authenticated before being processed here.

    Requests that set or change subscription properties should typically log the
    change through log_event.
    """
    def __call__(self, request, user_profile, property):
        property_method = getattr(self, "%s_%s" % (request.method.lower(), property), None)
        if not property_method:
            return json_error("Unknown property or invalid verb for %s" % (property,))

        return property_method(request, user_profile)

    def request_property(self, request_dict, property):
        return request_dict.get(property, "").strip()

    def get_stream_colors(self, request, user_profile):
        return json_success({"stream_colors": gather_subscriptions(user_profile)})

    def post_stream_colors(self, request, user_profile):
        stream_name = self.request_property(request.POST, "stream_name")
        if not stream_name:
            return json_error("Missing stream_name")
        color = self.request_property(request.POST, "color")
        if not color:
            return json_error("Missing color")

        set_stream_color(user_profile, stream_name, color)
        log_subscription_property_change(user_profile.user.email, "stream_color",
                                         {"stream_name": stream_name, "color": color})
        return json_success()

subscription_properties = SubscriptionProperties()

def make_property_call(request, query_dict, user_profile):
    property = query_dict.get("property").strip()
    if not property:
        return json_error("Missing property")

    return subscription_properties(request, user_profile, property.lower())

def make_get_property_call(request, user_profile):
    return make_property_call(request, request.GET, user_profile)

def make_post_property_call(request, user_profile):
    return make_property_call(request, request.POST, user_profile)

@authenticated_json_view
def json_subscription_property(request, user_profile):
    """
    This is the entry point to accessing or changing subscription
    properties. Authentication happens here.

    Add a handler for a new subscription property in SubscriptionProperties.
    """
    if request.method == "GET":
        return make_get_property_call(request, user_profile)
    elif request.method == "POST":
        return make_post_property_call(request, user_profile)
    else:
        return json_error("Invalid verb")

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request, username=POST, password=POST):
    user = authenticate(username=username, password=password)
    if user is None:
        return json_error("Your username or password is incorrect.", status=403)
    if not user.is_active:
        return json_error("Your account has been disabled.", status=403)
    return json_success({"api_key": user.userprofile.api_key})

@authenticated_json_post_view
@has_request_variables
def json_fetch_api_key(request, user_profile, password=POST):
    if not request.user.check_password(password):
        return json_error("Your username or password is incorrect.")
    return json_success({"api_key": user_profile.api_key})

class ActivityTable(object):
    def __init__(self, client_name, queries, default_tab=False):
        self.default_tab = default_tab
        self.has_pointer = False
        self.rows = {}
        for url, query_name in queries:
            if 'pointer' in query_name:
                self.has_pointer = True
            for record in UserActivity.objects.filter(
                    query=url,
                    client__name=client_name):
                row = self.rows.setdefault(record.user_profile.user.email, {})
                row['realm'] = record.user_profile.realm.domain
                row['full_name'] = record.user_profile.full_name
                row['username'] = record.user_profile.user.email.split('@')[0]
                row[query_name + '_count'] = record.count
                row[query_name + '_last' ] = record.last_visit

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
    return request.user.userprofile.realm.domain == 'humbughq.com'

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def get_activity(request):
    if not can_view_activity(request):
        return HttpResponseRedirect(reverse('zephyr.views.login_page'))

    web_queries = (
        ("/json/get_updates",    "get_updates"),
        ("/json/send_message",   "send_message"),
        ("/json/update_pointer", "update_pointer"),
    )

    api_queries = (
        ("/api/v1/get_messages",  "get_updates"),
        ("/api/v1/send_message",  "send_message"),
    )

    return render_to_response('zephyr/activity.html',
        { 'data': {
            'Website': ActivityTable('website',       web_queries, default_tab=True),
            'Mirror':  ActivityTable('zephyr_mirror', api_queries),
            'API':     ActivityTable('API',           api_queries),
            'Android': ActivityTable('Android',       api_queries),
            'iPhone':  ActivityTable('iPhone',        api_queries)
        }}, context_instance=RequestContext(request))

@authenticated_api_view
@has_request_variables
def api_github_landing(request, user_profile, event=POST,
                       payload=POST(converter=json_to_dict)):
    # TODO: this should all be moved to an external bot

    repository = payload['repository']

    if event == 'pull_request':
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
        subject = repository['name']
        if re.match(r'^0+$', payload['after']):
            content = "%s deleted branch %s" % (payload['pusher']['name'],
                                                short_ref)
        elif len(payload['commits']) == 0:
            content = ("%s [force pushed](%s) to branch %s.  Head is now %s"
                       % (payload['pusher']['name'],
                          payload['compare'],
                          short_ref,
                          payload['after'][:7]))
        else:
            content = ("%s [pushed](%s) to branch %s\n\n"
                       % (payload['pusher']['name'],
                          payload['compare'],
                          short_ref))
            num_commits = len(payload['commits'])
            max_commits = 10
            truncated_commits = payload['commits'][:max_commits]
            for commit in truncated_commits:
                short_id = commit['id'][:7]
                (short_commit_msg, _, _) = commit['message'].partition("\n")
                content += "* [%s](%s): %s\n" % (short_id, commit['url'],
                                                 short_commit_msg)
            if (num_commits > max_commits):
                content += ("\n[and %d more commits]"
                            % (num_commits - max_commits,))
    else:
        # We don't handle other events even though we get notified
        # about them
        return json_success()

    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[:57].rstrip() + '...'

    return send_message_backend(request, user_profile, get_client("github_bot"),
                                message_type_name="stream",
                                message_to=["commits"],
                                forged=False, subject_name=subject,
                                message_content=content)
