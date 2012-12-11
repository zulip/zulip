from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.timezone import utc, now
from django.core.exceptions import ValidationError
from django.contrib.auth.views import login as django_login_page
from django.db.models import Q
from zephyr.models import Message, UserProfile, Stream, Subscription, \
    Recipient, get_display_recipient, get_huddle, Realm, UserMessage, \
    do_add_subscription, do_remove_subscription, do_change_password, \
    do_change_full_name, do_change_enable_desktop_notifications, \
    do_activate_user, add_default_subs, do_create_user, do_send_message, \
    create_mit_user_if_needed, create_stream_if_needed, StreamColor, \
    PreregistrationUser, get_client, MitUser, User, UserActivity, \
    log_subscription_property_change, internal_send_message, \
    MAX_SUBJECT_LENGTH, MAX_MESSAGE_LENGTH
from zephyr.forms import RegistrationForm, HomepageForm, is_unique, \
    is_active
from django.views.decorators.csrf import csrf_exempt

from zephyr.decorator import asynchronous, require_post, \
    authenticated_api_view, authenticated_json_post_view, \
    internal_notify_view, RespondAsynchronously, \
    has_request_variables, POST, authenticated_json_view
from zephyr.lib.query import last_n
from zephyr.lib.avatar import gravatar_hash
from zephyr.lib.response import json_success, json_error
from zephyr.lib.time import timestamp_to_datetime

from confirmation.models import Confirmation

import datetime
import simplejson
import socket
import re
import urllib
import time
import requests
import os
import base64

SERVER_GENERATION = int(time.time())

def to_non_negative_int(x):
    x = int(x)
    if x < 0:
        raise ValueError("argument is negative")
    return x

def json_to_dict(json):
    data = simplejson.loads(json)
    if not isinstance(data, dict):
        raise ValueError("argument is not a dictionary")
    return data

def json_to_list(json):
    data = simplejson.loads(json)
    if not isinstance(data, list):
        raise ValueError("argument is not a list")
    return data

def get_stream(stream_name, realm):
    try:
        return Stream.objects.get(name__iexact=stream_name, realm=realm)
    except Stream.DoesNotExist:
        return None

def notify_new_user(user_profile, internal=False):
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    internal_send_message("humbug+signups@humbughq.com",
            Recipient.STREAM, "signups", user_profile.realm.domain,
            "%s <`%s`> just signed up for Humbug!%s(total: **%i**)" % (
                user_profile.full_name,
                user_profile.user.email,
                internal_blurb,
                UserProfile.objects.filter(realm=user_profile.realm,
                                           user__is_active=True).count(),
                )
            )

@require_post
def accounts_register(request):
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    email = confirmation.content_object.email
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
                add_default_subs(user_profile)

            notify_new_user(user_profile)

            login(request, authenticate(username=email, password=password))
            return HttpResponseRedirect(reverse('zephyr.views.home'))

    return render_to_response('zephyr/register.html',
        { 'form': form, 'company_name': company_name, 'email': email, 'key': key },
        context_instance=RequestContext(request))

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
            try:
                email = form.cleaned_data['email']
                user = PreregistrationUser.objects.get(email=email)
            except PreregistrationUser.DoesNotExist:
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

    # Populate personals autocomplete list based on everyone in your
    # realm.  Later we might want a 2-layer autocomplete, where we
    # consider specially some sort of "buddy list" who e.g. you've
    # talked to before, but for small organizations, the right list is
    # everyone in your realm.
    people = [{'email'     : profile.user.email,
               'full_name' : profile.full_name}
              for profile in
              UserProfile.objects.select_related().filter(realm=user_profile.realm) if
              profile != user_profile]

    subscriptions = Subscription.objects.select_related().filter(user_profile_id=user_profile, active=True)
    streams = [get_display_recipient(sub.recipient) for sub in subscriptions
               if sub.recipient.type == Recipient.STREAM]

    return render_to_response('zephyr/index.html',
                              {'user_profile': user_profile,
                               'email_hash'  : gravatar_hash(user_profile.user.email),
                               'people'      : people,
                               'streams'     : streams,
                               'poll_timeout': settings.POLL_TIMEOUT,
                               'have_initial_messages':
                                   'true' if num_messages > 0 else 'false',
                               'show_debug':
                                   settings.DEBUG and ('show_debug' in request.GET),
                               'show_activity': can_view_activity(request) },
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
def update_pointer_backend(request, user_profile, updater, pointer=POST(converter=int)):
    if pointer < 0:
        return json_error("Invalid pointer value")

    if pointer <= user_profile.pointer:
        return json_success()

    user_profile.pointer = pointer
    user_profile.last_pointer_updater = updater
    user_profile.save()

    if settings.TORNADO_SERVER:
        requests.post(settings.TORNADO_SERVER + '/notify_pointer_update', data=dict(
            secret          = settings.SHARED_SECRET,
            user            = user_profile.user.id,
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

@has_request_variables
def get_old_messages_backend(request, anchor = POST(converter=to_non_negative_int),
                             num_before = POST(converter=to_non_negative_int),
                             num_after = POST(converter=to_non_negative_int),
                             narrow = POST('narrow', converter=json_to_dict),
                             user_profile=None, apply_markdown=True):
    query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')

    if 'recipient_id' in narrow:
        query = query.filter(recipient_id = narrow['recipient_id'])
    if 'stream' in narrow:
        try:
            stream = Stream.objects.get(realm=user_profile.realm, name__iexact=narrow['stream'])
        except Stream.DoesNotExist:
            return json_error("Invalid stream %s" % (narrow['stream'],))
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
        query = query.filter(recipient_id = recipient.id)

    if 'one_on_one_email' in narrow:
        query = query.filter(recipient__type=Recipient.PERSONAL)
        try:
            recipient_user = UserProfile.objects.get(user__email = narrow['one_on_one_email'])
        except UserProfile.DoesNotExist:
            return json_error("Invalid one_on_one_email %s" % (narrow['one_on_one_email'],))
        recipient = Recipient.objects.get(type=Recipient.PERSONAL, type_id=recipient_user.id)
        # If we are narrowed to personals with ourself, we want to search for personals where the user
        # with address "one_on_one_email" is the sender *and* the recipient, not personals where the user
        # with address "one_on_one_email is the sender *or* the recipient.
        if narrow['one_on_one_email'] == user_profile.user.email:
            query = query.filter(Q(sender__user__email=narrow['one_on_one_email']) & Q(recipient=recipient))
        else:
            query = query.filter(Q(sender__user__email=narrow['one_on_one_email']) | Q(recipient=recipient))
    elif 'type' in narrow and (narrow['type'] == "private" or narrow['type'] == "all_private_messages"):
        query = query.filter(Q(recipient__type=Recipient.PERSONAL) | Q(recipient__type=Recipient.HUDDLE))

    if 'subject' in narrow:
        query = query.filter(subject = narrow['subject'])

    if 'searchterm' in narrow:
        query = query.filter(Q(content__icontains=narrow['searchterm']) |
                             Q(subject__icontains=narrow['searchterm']))

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

@asynchronous
@authenticated_json_post_view
def json_get_updates(request, user_profile, handler):
    client_id = request.session.session_key
    return get_updates_backend(request, user_profile, handler, client_id,
                               client=request._client, apply_markdown=True)

@asynchronous
@authenticated_api_view
@has_request_variables
def api_get_messages(request, user_profile, handler, client_id=POST(default=None),
                     apply_markdown=POST(default=False, converter=simplejson.loads)):
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=apply_markdown,
                               client=request._client)

def format_updates_response(messages=[], apply_markdown=True,
                            user_profile=None, new_pointer=None,
                            client=None, update_types=[],
                            client_server_generation=None):
    if client is not None and client.name.endswith("_mirror"):
        messages = [m for m in messages if m.sending_client.name != client.name]
    ret = {'messages': [message.to_dict(apply_markdown) for message in messages],
           "result": "success",
           "msg": "",
           'update_types': update_types}
    if client_server_generation is not None:
        ret['server_generation'] = SERVER_GENERATION
    if new_pointer is not None:
        ret['new_pointer'] = new_pointer
    if user_profile.realm.domain == "mit.edu":
        try:
            activity = UserActivity.objects.get(user_profile = user_profile,
                                                query="/api/v1/get_messages",
                                                client__name="zephyr_mirror")
            ret['zephyr_mirror_active'] = \
                (activity.last_visit.replace(tzinfo=None) >
                 datetime.datetime.utcnow() - datetime.timedelta(minutes=5))
        except UserActivity.DoesNotExist:
            ret['zephyr_mirror_active'] = False

    return ret

def return_messages_immediately(user_profile, client_id, last,
                                client_server_generation,
                                client_pointer, dont_block, **kwargs):
    if last is None:
        # When an API user is first querying the server to subscribe,
        # there's no reason to reply immediately.
        # TODO: Make this work with server_generation
        return None

    if UserMessage.objects.filter(user_profile=user_profile).count() == 0:
        # The client has no messages, so we should immediately start long-polling
        return None

    if last < 0:
        return {"msg": "Invalid 'last' argument", "result": "error"}

    new_pointer = None
    query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')

    messages = query.filter(id__gt=last)[:400]

    # Filter for mirroring before checking whether there are any
    # messages to pass on.  If we don't do this, when the only message
    # to forward is one that was sent via the mirroring, the API
    # client will end up in an endless loop requesting more data from
    # us.
    if "client" in kwargs and kwargs["client"].name.endswith("_mirror"):
        messages = [m for m in messages if
                    m.sending_client.name != kwargs["client"].name]

    update_types = []
    if messages:
        update_types.append("new_messages")

    if dont_block:
        update_types.append("nonblocking_request")

    if (client_server_generation is not None and
        client_server_generation != SERVER_GENERATION):
        update_types.append("client_reload")

    ptr = user_profile.pointer
    if (client_pointer is not None and ptr > client_pointer):
        new_pointer = ptr
        update_types.append("pointer_update")

    if update_types:
        return format_updates_response(messages=messages,
                                       user_profile=user_profile,
                                       new_pointer=new_pointer,
                                       client_server_generation=client_server_generation,
                                       update_types=update_types,
                                       **kwargs)

    return None

def send_with_safety_check(response, handler, apply_markdown=True, **kwargs):
    # Make sure that Markdown rendering really happened, if requested.
    # This is a security issue because it's where we escape HTML.
    # c.f. ticket #64
    #
    # apply_markdown=True is the fail-safe default.
    if response['result'] == 'success' and apply_markdown:
        for msg in response['messages']:
            if msg['content_type'] != 'text/html':
                handler.set_status(500)
                handler.finish('Internal error: bad message format')
                return
    if response['result'] == 'error':
        handler.set_status(400)
    handler.finish(response)

@has_request_variables
def get_updates_backend(request, user_profile, handler, client_id,
                        last = POST(converter=int, default=None),
                        client_server_generation = POST(whence='server_generation', default=None,
                                                        converter=int),
                        client_pointer = POST(whence='pointer', converter=int, default=None),
                        dont_block = POST(converter=simplejson.loads, default=False),
                        **kwargs):
    resp = return_messages_immediately(user_profile, client_id, last,
                                       client_server_generation,
                                       client_pointer,
                                       dont_block, **kwargs)
    if resp is not None:
        send_with_safety_check(resp, handler, **kwargs)

        # We have already invoked handler.finish(), so we bypass the usual view
        # response path.  We are "responding asynchronously" except that it
        # already happened.  This is slightly weird, but lets us share
        # send_with_safety_check with the code below.
        return RespondAsynchronously

    # Enter long-polling mode.
    #
    # Instead of responding to the client right away, leave our connection open
    # and return to the Tornado main loop.  One of the notify_* views will
    # eventually invoke one of these callbacks, which will send the delayed
    # response.

    def cb(**cb_kwargs):
        if handler.request.connection.stream.closed():
            return
        try:
            # It would be nice to be able to do these checks in
            # UserProfile.receive, but it doesn't know what the value
            # of "last" was for each callback.
            if last is not None and "messages" in cb_kwargs:
                messages = cb_kwargs["messages"]

                # Make sure the client doesn't get a message twice
                # when messages are processed out of order.
                if messages[0].id <= last:
                    # We must return a response because we don't have
                    # a way to re-queue a callback and so the client
                    # must do it by making a new request
                    handler.finish({"result": "success",
                                    "msg": "",
                                    'update_types': []})
                    return

                # We need to check whether there are any new messages
                # between the client's get_updates call and the
                # message we're about to return to the client and
                # return them as well or the client will miss them.
                # See #174.
                extra_messages = (Message.objects.select_related()
                                  .filter(usermessage__user_profile = user_profile,
                                          id__gt = last,
                                          id__lt = messages[0].id)
                                  .order_by('id'))
                if extra_messages:
                    new_messages = list(extra_messages)
                    new_messages.append(messages[0])
                    cb_kwargs["messages"] = new_messages

            kwargs.update(cb_kwargs)
            res = format_updates_response(user_profile=user_profile,
                                          client_server_generation=client_server_generation,
                                          **kwargs)
            send_with_safety_check(res, handler, **kwargs)
        except socket.error:
            pass

    user_profile.add_receive_callback(handler.async_callback(cb))
    if client_pointer is not None:
        user_profile.add_pointer_update_callback(handler.async_callback(cb))

    # runtornado recognizes this special return value.
    return RespondAsynchronously

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

        try:
            stream = Stream.objects.get(realm=user_profile.realm, name__iexact=stream_name)
        except Stream.DoesNotExist:
            return json_error("Stream does not exist")
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    elif message_type_name == 'private':
        recipient_profile_ids = set()
        for email in message_to:
            try:
                recipient_profile_ids.add(UserProfile.objects.get(user__email__iexact=email).id)
            except UserProfile.DoesNotExist:
                return json_error("Invalid email '%s'" % (email,))

        if client.name == "zephyr_mirror":
            if user_profile.id not in recipient_profile_ids and not forged:
                return json_error("User not authorized for this query")

        # If the private message is just between the sender and
        # another person, force it to be a personal internally
        if (len(recipient_profile_ids) == 2
            and sender.id in recipient_profile_ids):
            recipient_profile_ids.remove(sender.id)

        if len(recipient_profile_ids) > 1:
            # Make sure the sender is included in huddle messages
            recipient_profile_ids.add(sender.id)
            huddle = get_huddle(list(recipient_profile_ids))
            recipient = Recipient.objects.get(type_id=huddle.id, type=Recipient.HUDDLE)
        else:
            recipient = Recipient.objects.get(type_id=list(recipient_profile_ids)[0],
                                              type=Recipient.PERSONAL)
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

@internal_notify_view
def notify_new_message(request):
    # If a message for some reason has no recipients (e.g. it is sent
    # by a bot to a stream that nobody is subscribed to), just skip
    # the message gracefully
    if request.POST["users"] == "":
        return json_success()

    # FIXME: better query
    users   = [UserProfile.objects.get(id=user)
               for user in json_to_list(request.POST['users'])]
    message = Message.objects.get(id=request.POST['message'])

    # Cause message.to_dict() to return the dicts already rendered in the other process.
    #
    # We decode this JSON only to eventually re-encode it as JSON.
    # This isn't trivial to fix, because we do access some fields in the meantime
    # (see send_with_safety_check).  It's probably not a big deal.
    message.precomputed_dicts = simplejson.loads(request.POST['rendered'])

    for user in users:
        user.receive(message)

    return json_success()

@internal_notify_view
def notify_pointer_update(request):
    # FIXME: better query
    user_profile = UserProfile.objects.get(id=request.POST['user'])
    new_pointer = int(request.POST['new_pointer'])
    pointer_updater = request.POST['pointer_updater']

    user_profile.update_pointer(new_pointer, pointer_updater)

    return json_success()

@authenticated_api_view
def api_get_public_streams(request, user_profile):
    # Only get streams someone is currently subscribed to
    subs_filter = Subscription.objects.filter(active=True).values('recipient_id')
    stream_ids = Recipient.objects.filter(
        type=Recipient.STREAM, id__in=subs_filter).values('type_id')
    streams = sorted(stream.name for stream in
                     Stream.objects.filter(id__in = stream_ids,
                                           realm=user_profile.realm))
    return json_success({"streams": streams})

default_stream_color = "#c2c2c2"

def get_stream_color(sub):
    try:
        return StreamColor.objects.get(subscription=sub).color
    except StreamColor.DoesNotExist:
        return default_stream_color

def gather_subscriptions(user_profile):
    # This is a little awkward because the StreamColor table has foreign keys
    # to Subscription, but not vice versa, and not all Subscriptions have a
    # StreamColor.
    #
    # We could do this with a single OUTER JOIN query but Django's ORM does
    # not provide a simple way to specify one.

    # For now, don't display the subscription for your ability to receive personals.
    subs = Subscription.objects.filter(
        user_profile    = user_profile,
        active          = True,
        recipient__type = Recipient.STREAM)
    with_color = StreamColor.objects.filter(subscription__in = subs).select_related()
    no_color   = subs.exclude(id__in = with_color.values('subscription_id')).select_related()

    result = [(get_display_recipient(sc.subscription.recipient), sc.color)
        for sc in with_color]
    result.extend((get_display_recipient(sub.recipient), default_stream_color)
        for sub in no_color)

    return sorted(result)

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
                              streams_raw = POST('subscriptions', json_to_list)):
    stream_names = []
    for stream_name in streams_raw:
        stream_name = stream_name.strip()
        if len(stream_name) > 30:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name (%s)." % (stream_name,))
        stream_names.append(stream_name)

    result = dict(subscribed=[], already_subscribed=[])
    for stream_name in set(stream_names):
        stream = create_stream_if_needed(user_profile.realm, stream_name)
        did_subscribe = do_add_subscription(user_profile, stream)
        if did_subscribe:
            result["subscribed"].append(stream_name)
        else:
            result["already_subscribed"].append(stream_name)

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_change_settings(request, user_profile, full_name=POST,
                         old_password=POST, new_password=POST,
                         confirm_password=POST,
                         # enable_desktop_notification needs to default to False
                         # because browsers POST nothing for an unchecked checkbox
                         enable_desktop_notifications=POST(converter=lambda x: x == "on",
                                                           default=False)):
    if new_password != "":
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
            'API':     ActivityTable('API',           api_queries)
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
