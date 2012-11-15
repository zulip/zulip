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
    do_change_full_name, do_activate_user, \
    create_user, do_send_message, create_mit_user_if_needed, \
    create_stream_if_needed, PreregistrationUser, get_client, MitUser, \
    User, UserActivity
from zephyr.forms import RegistrationForm, HomepageForm, is_unique, \
    is_active
from django.views.decorators.csrf import csrf_exempt

from zephyr.decorator import asynchronous, require_post, \
    authenticated_api_view, authenticated_json_view, \
    has_request_variables, POST
from zephyr.lib.query import last_n
from zephyr.lib.avatar import gravatar_hash
from zephyr.lib.response import json_success, json_error

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
    assert x >= 0
    return x

def get_stream(stream_name, realm):
    try:
        return Stream.objects.get(name__iexact=stream_name, realm=realm)
    except Stream.DoesNotExist:
        return None

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

            if mit_beta_user:
                user = User.objects.get(email=email)
                do_activate_user(user)
                do_change_password(user, password)
                do_change_full_name(user.userprofile, full_name)
            else:
                # FIXME: sanitize email addresses
                create_user(email, password, realm, full_name, short_name)

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
    return render_to_response('zephyr/accounts_home.html',
                              context_instance=RequestContext(request))

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def home(request):
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
                               'have_initial_messages':
                                   'true' if num_messages > 0 else 'false',
                               'show_debug':
                                   settings.DEBUG and ('show_debug' in request.GET) },
                              context_instance=RequestContext(request))

@authenticated_api_view
@has_request_variables
def api_update_pointer(request, user_profile, updater=POST('client_id')):
    return update_pointer_backend(request, user_profile, updater)

@authenticated_json_view
def json_update_pointer(request, user_profile):
    return update_pointer_backend(request, user_profile,
                                  request.session.session_key)

@has_request_variables
def update_pointer_backend(request, user_profile, updater, pointer=POST(converter=int)):
    if pointer < 0:
        return json_error("Invalid pointer value")

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

@authenticated_json_view
def json_get_old_messages(request, user_profile):
    return get_old_messages_backend(request, user_profile=user_profile,
                                    apply_markdown=True)

@authenticated_api_view
@has_request_variables
def api_get_old_messages(request, user_profile, apply_markdown=POST(default=False)):
    return get_old_messages_backend(request, user_profile=user_profile,
                                    apply_markdown=apply_markdown)

@has_request_variables
def get_old_messages_backend(request, anchor = POST(converter=to_non_negative_int),
                             num_before = POST(converter=to_non_negative_int),
                             num_after = POST(converter=to_non_negative_int),
                             narrow = POST('narrow', converter=simplejson.loads),
                             user_profile=None, apply_markdown=True):
    query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')

    if 'recipient_id' in narrow:
        query = query.filter(recipient_id = narrow['recipient_id'])

    if 'one_on_one_email' in narrow:
        query = query.filter(recipient__type=Recipient.PERSONAL)
        recipient_user = UserProfile.objects.get(user__email = narrow['one_on_one_email'])
        recipient = Recipient.objects.get(type=Recipient.PERSONAL, type_id=recipient_user.id)
        query = query.filter(Q(sender__user__email=narrow['one_on_one_email']) | Q(recipient=recipient))
    elif 'type' in narrow and (narrow['type'] == "huddle" or narrow['type'] == "all_huddles"):
        query = query.filter(Q(recipient__type=Recipient.PERSONAL) | Q(recipient__type=Recipient.HUDDLE))

    if 'subject' in narrow:
        query = query.filter(subject = narrow['subject'])

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
@authenticated_json_view
def json_get_updates(request, user_profile, handler):
    client_id = request.session.session_key
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=True)

@asynchronous
@authenticated_api_view
@has_request_variables
def api_get_messages(request, user_profile, handler, client_id=POST(default=None)):
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=(request.POST.get("apply_markdown") is not None),
                               mirror=request.POST.get("mirror"))

def format_updates_response(messages=[], apply_markdown=True,
                            user_profile=None, new_pointer=None,
                            mirror=None, update_types=[]):
    if mirror is not None:
        messages = [m for m in messages if m.sending_client.name != mirror]
    ret = {'messages': [message.to_dict(apply_markdown) for message in messages],
           "result": "success",
           "msg": "",
           'server_generation': SERVER_GENERATION,
           'update_types': update_types}
    if new_pointer is not None:
        ret['new_pointer'] = new_pointer
    return ret

def format_delayed_updates_response(request=None, user_profile=None,
                                    new_pointer=None, pointer_updater=None,
                                    client_id=None, update_types=[],
                                    **kwargs):
    client_pointer = request.POST.get("pointer")
    client_wants_ptr_updates = False
    if client_pointer is not None:
        client_pointer = int(client_pointer)
        client_wants_ptr_updates = True

    pointer = None
    if (client_wants_ptr_updates
          and str(pointer_updater) != str(client_id)
          and client_pointer != new_pointer):
        pointer = new_pointer
        update_types.append("pointer_update")

    return format_updates_response(new_pointer=pointer,
                                   update_types=update_types, **kwargs)

def return_messages_immediately(user_profile, client_id, last,
                                failures, client_server_generation,
                                client_reload_pending, **kwargs):
    if last is None:
        # When an API user is first querying the server to subscribe,
        # there's no reason to reply immediately.
        # TODO: Make this work with server_generation/failures
        return None

    if UserMessage.objects.filter(user_profile=user_profile).count() == 0:
        # The client has no messages, so we should immediately start long-polling
        return None

    if last < 0:
        return {"msg": "Invalid 'last' argument", "result": "error"}

    # Pointer sync is disabled for now
    # client_pointer = request.POST.get("pointer")

    # Pointer sync is disabled for now
    # client_wants_ptr_updates = False
    # if client_pointer is not None:
    #     client_pointer = int(client_pointer)
    #     client_wants_ptr_updates = True

    new_pointer = None
    query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')
    # Pointer sync is disabled for now
    # ptr = user_profile.pointer

    messages = query.filter(id__gt=last)[:400]

    # Filter for mirroring before checking whether there are any
    # messages to pass on.  If we don't do this, when the only message
    # to forward is one that was sent via the mirroring, the API
    # client will end up in an endless loop requesting more data from
    # us.
    if "mirror" in kwargs:
        messages = [m for m in messages if
                    m.sending_client.name != kwargs["mirror"]]

    update_types = []
    if messages:
        update_types.append("new_messages")

    if (client_server_generation is not None
        and int(client_server_generation) != SERVER_GENERATION
        and not client_reload_pending):
        update_types.append("client_reload")

    # Pointer sync is disabled for now
    # if (client_wants_ptr_updates
    #       and str(user_profile.last_pointer_updater) != str(client_id)
    #       and ptr != client_pointer):
    #     new_pointer = ptr
    #     update_types.append("pointer_update")

    if failures >= 1:
        update_types.append("reset_failure_counter")

    if update_types:
        return format_updates_response(messages=messages,
                                       user_profile=user_profile,
                                       new_pointer=new_pointer,
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
                        failures = POST(converter=int, default=None),
                        client_server_generation = POST(whence='server_generation', default=None),
                        client_reload_pending = POST(whence='server_generation', default=None),
                        **kwargs):
    resp = return_messages_immediately(user_profile, client_id, last, failures,
                                       client_server_generation,
                                       client_reload_pending, **kwargs)
    if resp is not None:
        send_with_safety_check(resp, handler, **kwargs)
        return

    # Now we're in long-polling mode

    def cb(**cb_kwargs):
        if handler.request.connection.stream.closed():
            return
        try:
            kwargs.update(cb_kwargs)
            res = format_delayed_updates_response(request=request,
                                                  user_profile=user_profile,
                                                  client_id=client_id,
                                                  **kwargs)
            send_with_safety_check(res, handler, **kwargs)
        except socket.error:
            pass

    user_profile.add_receive_callback(handler.async_callback(cb))
    user_profile.add_pointer_update_callback(handler.async_callback(cb))

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
@has_request_variables
def api_send_message(request, user_profile,
                     client_name=POST("client", default="API")):
    return send_message_backend(request, user_profile, client_name)

@authenticated_json_view
@has_request_variables
def json_send_message(request, user_profile,
                      client_name=POST("client", default="website")):
    return send_message_backend(request, user_profile, client_name)

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
        recipients = simplejson.loads(raw_recipients)
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
def send_message_backend(request, user_profile, client_name,
                         message_type_name = POST('type'),
                         message_to = POST('to', converter=extract_recipients),
                         forged = POST(default=False),
                         message_content = POST('content')):
    is_super_user = is_super_user_api(request)
    if forged and not is_super_user:
        return json_error("User not authorized for this query")

    if len(message_to) == 0:
        return json_error("Message must have recipients.")

    if client_name == "zephyr_mirror":
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
        if "subject" not in request.POST:
            return json_error("Missing subject")
        if len(message_to) > 1:
            return json_error("Cannot send to multiple streams")
        stream_name = message_to[0].strip()
        subject_name = request.POST['subject'].strip()
        if stream_name == "":
            return json_error("Stream can't be empty")
        if subject_name == "":
            return json_error("Subject can't be empty")
        if len(stream_name) > 30:
            return json_error("Stream name too long")
        if len(subject_name) > 60:
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

        if client_name == "zephyr_mirror":
            if user_profile.id not in recipient_profile_ids and not forged:
                return json_error("User not authorized for this query")

        # If the private message is just between the sender and
        # another person, force it to be a personal internally
        if (len(recipient_profile_ids) == 2
            and user_profile.id in recipient_profile_ids):
            recipient_profile_ids.remove(user_profile.id)

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
        message.pub_date = datetime.datetime.utcfromtimestamp(float(request.POST['time'])).replace(tzinfo=utc)
    else:
        message.pub_date = now()
    message.sending_client = get_client(client_name)

    if client_name == "zephyr_mirror" and already_sent_mirrored_message(message):
        return json_success()

    do_send_message(message)

    return json_success()

def validate_notify(request):
    # Check the shared secret.
    # Also check the originating IP, at least for now.
    return (request.META['REMOTE_ADDR'] in ('127.0.0.1', '::1')
            and request.POST.get('secret') == settings.SHARED_SECRET)


@csrf_exempt
@require_post
def notify_new_message(request):
    if not validate_notify(request):
        return json_error("Access denied", status=403)

    # If a message for some reason has no recipients (e.g. it is sent
    # by a bot to a stream that nobody is subscribed to), just skip
    # the message gracefully
    if request.POST["users"] == "":
        return json_success()

    # FIXME: better query
    users   = [UserProfile.objects.get(id=user)
               for user in request.POST['users'].split(',')]
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

@csrf_exempt
@require_post
def notify_pointer_update(request):
    if not validate_notify(request):
        return json_error("Access denied", status=403)

    # FIXME: better query
    user_profile = UserProfile.objects.get(id=request.POST['user'])
    new_pointer = int(request.POST['new_pointer'])
    pointer_updater = request.POST['pointer_updater']

    user_profile.update_pointer(new_pointer, pointer_updater)

    return json_success()

@authenticated_api_view
def api_get_public_streams(request, user_profile):
    streams = sorted(stream.name for stream in
                     Stream.objects.filter(realm=user_profile.realm))
    return json_success({"streams": streams})

def gather_subscriptions(user_profile):
    subscriptions = Subscription.objects.filter(user_profile=user_profile, active=True)
    # For now, don't display the subscription for your ability to receive personals.
    return sorted(get_display_recipient(sub.recipient)
                  for sub in subscriptions
                  if sub.recipient.type == Recipient.STREAM)

@authenticated_api_view
def api_get_subscriptions(request, user_profile):
    return json_success({"streams": gather_subscriptions(user_profile)})

@authenticated_json_view
def json_list_subscriptions(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)})

@authenticated_json_view
@has_request_variables
def json_remove_subscription(request, user_profile,
                             sub_name=POST("subscription")):
    stream = get_stream(sub_name, user_profile.realm)
    if not stream:
        return json_error("Stream does not exist")
    did_remove = do_remove_subscription(user_profile, stream)
    if not did_remove:
        return json_error("Not subscribed, so you can't unsubscribe")

    return json_success({"data": sub_name})

def valid_stream_name(name):
    return name != ""

@authenticated_api_view
def api_subscribe(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

@authenticated_json_view
def json_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

@has_request_variables
def add_subscriptions_backend(request, user_profile, streams_raw = POST('streams', simplejson.loads)):
    streams = []
    for stream_name in streams_raw:
        stream_name = stream_name.strip()
        if len(stream_name) > 30:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name (%s)." % (stream_name,))
        streams.append(stream_name)

    subscribed = []
    already_subscribed = []
    for stream_name in set(streams):
        stream = create_stream_if_needed(user_profile.realm, stream_name)
        did_subscribe = do_add_subscription(user_profile, stream)
        if did_subscribe:
            subscribed.append(stream_name)
        else:
            already_subscribed.append(stream_name)

    return json_success({"subscribed": subscribed,
                         "already_subscribed": already_subscribed})

@authenticated_json_view
@has_request_variables
def json_change_settings(request, user_profile, full_name=POST,
                         old_password=POST, new_password=POST,
                         confirm_password=POST):
    if new_password != "":
        if new_password != confirm_password:
            return json_error("New password must match confirmation password!")
        if not authenticate(username=user_profile.user.email, password=old_password):
            return json_error("Wrong password!")
        do_change_password(user_profile.user, new_password)

    result = {}
    if user_profile.full_name != full_name:
        do_change_full_name(user_profile, full_name)
        result['full_name'] = full_name

    return json_success(result)

@authenticated_json_view
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

@authenticated_json_view
@has_request_variables
def json_fetch_api_key(request, user_profile, password=POST):
    if not request.user.check_password(password):
        return json_error("Your username or password is incorrect.")
    return json_success({"api_key": user_profile.api_key})

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def get_activity(request):
    user_profile = request.user.userprofile
    if user_profile.realm.domain != "humbughq.com":
        return HttpResponseRedirect(reverse('zephyr.views.login_page'))

    def add_activity(activity, url, query_name, client_name):
        for row in UserActivity.objects.filter(query=url,
                                               client__name=client_name):
            email = row.user_profile.user.email
            activity.setdefault(email, {})
            activity[email]['email'] = email
            activity[email][query_name + '_count'] = row.count
            activity[email][query_name + '_last'] = row.last_visit

    website_activity = {}
    add_activity(website_activity, "/json/get_updates", "get_updates", "website")
    add_activity(website_activity, "/json/send_message", "send_message", "website")
    add_activity(website_activity, "/json/update_pointer", "update_pointer", "website")

    mirror_activity = {}
    add_activity(mirror_activity, "/api/v1/get_messages", "get_updates", "zephyr_mirror")
    add_activity(mirror_activity, "/api/v1/send_message", "send_message", "zephyr_mirror")

    api_activity = {}
    add_activity(api_activity, "/api/v1/get_messages", "get_updates", "API")
    add_activity(api_activity, "/api/v1/send_message", "send_message", "API")

    return render_to_response('zephyr/activity.html',
        { 'data': [
            ('Website', True,  website_activity.values()),
            ('Mirror',  False, mirror_activity.values()),
            ('API',     False, api_activity.values())
        ]}, context_instance=RequestContext(request))
