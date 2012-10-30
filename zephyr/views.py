from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.timezone import utc
from django.core.exceptions import ValidationError
from django.contrib.auth.views import login as django_login_page
from zephyr.models import Message, UserProfile, Stream, Subscription, \
    Recipient, get_display_recipient, get_huddle, Realm, UserMessage, \
    do_add_subscription, do_remove_subscription, do_change_password, \
    do_change_full_name, do_activate_user, \
    create_user, do_send_message, create_user_if_needed, \
    create_stream_if_needed, PreregistrationUser, get_client, MitUser, \
    User
from zephyr.forms import RegistrationForm, HomepageForm, is_unique, \
    is_active
from django.views.decorators.csrf import csrf_exempt

from zephyr.decorator import asynchronous
from zephyr.lib.query import last_n
from zephyr.lib.avatar import gravatar_hash

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

def require_post(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.method != "POST":
            return json_error('This form can only be submitted by POST.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

# api_key_required will add the authenticated user's user_profile to
# the view function's arguments list, since we have to look it up
# anyway.
def login_required_api_view(view_func):
    @csrf_exempt
    @require_post
    def _wrapped_view_func(request, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(user__email=request.POST.get("email"))
        except UserProfile.DoesNotExist:
            return json_error("Invalid user")
        if user_profile is None or request.POST.get("api-key") != user_profile.api_key:
            return json_error('Invalid API user/key pair.')
        return view_func(request, user_profile, *args, **kwargs)
    return _wrapped_view_func

# Checks if the request is a POST request and that the user is logged
# in.  If not, return an error (the @login_required behavior of
# redirecting to a login page doesn't make sense for json views)
def login_required_json_view(view_func):
    @require_post
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated():
            return json_error("Not logged in")
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def json_response(res_type="success", msg="", data={}, status=200):
    content = {"result": res_type, "msg": msg}
    content.update(data)
    return HttpResponse(content=simplejson.dumps(content),
                        mimetype='application/json', status=status)

def json_success(data={}):
    return json_response(data=data)

def json_error(msg, data={}, status=400):
    return json_response(res_type="error", msg=msg, data=data, status=status)

def get_stream(stream_name, realm):
    stream = Stream.objects.filter(name__iexact=stream_name, realm=realm)
    if stream:
        return stream[0]
    else:
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

@login_required_api_view
def api_update_pointer(request, user_profile):
    updater = request.POST.get("client_id")
    if updater is None:
        return json_error("Missing client_id argument")
    return update_pointer_backend(request, user_profile, updater)

@login_required_json_view
def json_update_pointer(request):
    user_profile = UserProfile.objects.get(user=request.user)
    return update_pointer_backend(request, user_profile,
                                  request.session.session_key)

def update_pointer_backend(request, user_profile, updater):
    pointer = request.POST.get('pointer')
    if not pointer:
        return json_error("Missing pointer")

    try:
        pointer = int(pointer)
    except ValueError:
        return json_error("Invalid pointer: must be an integer")

    if pointer < 0:
        return json_error("Invalid pointer value")

    user_profile.pointer = pointer
    user_profile.last_pointer_updater = updater
    user_profile.save()

    if settings.HAVE_TORNADO_SERVER:
        requests.post(settings.NOTIFY_POINTER_UPDATE_URL, data=[
               ('secret',  settings.SHARED_SECRET),
               ('user', user_profile.user.id),
               ('new_pointer', pointer),
               ('pointer_updater', updater)])

    return json_success()

@login_required_json_view
def json_get_old_messages(request):
    user_profile = UserProfile.objects.get(user=request.user)
    return get_old_messages_backend(request, user_profile=user_profile,
                                    apply_markdown=True)

@login_required_api_view
def api_get_old_messages(request, user_profile):
    return get_old_messages_backend(request, user_profile=user_profile,
                                    apply_markdown=(request.POST.get("apply_markdown") is not None))

def get_old_messages_backend(request, user_profile=None,
                             apply_markdown=True):
    if not ('start' in request.POST):
        return json_error("Missing 'start' parameter")
    if not ('which' in request.POST):
        return json_error("Missing 'which' parameter")
    if not ('number' in request.POST):
        return json_error("Missing 'number' parameter")

    start = int(request.POST.get("start"))
    which = request.POST.get("which")
    number = int(request.POST.get("number"))

    query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')

    if which == "older":
        messages = last_n(number, query.filter(id__lte=start))
    elif which == "newer":
        messages = query.filter(id__gte=start)[:number]
    elif which == "around":
        num_older = number / 2
        num_newer = number / 2
        if number % 2 != 0:
            num_older += 1
        messages = (last_n(num_older, query.filter(id__lte=start))
                    + list(query.filter(id__gt=start)[:num_newer]))
    else:
        return json_error("Bad value for 'which' argument")

    ret = {'messages': [message.to_dict(apply_markdown) for message in messages],
           "result": "success",
           "msg": "",
           'server_generation': SERVER_GENERATION}
    return json_success(ret)

@asynchronous
@login_required_json_view
def json_get_updates(request, handler):
    user_profile = UserProfile.objects.get(user=request.user)
    client_id = request.session.session_key
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=True)

@asynchronous
@login_required_api_view
def api_get_messages(request, user_profile, handler):
    client_id = request.POST.get("client_id")
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=(request.POST.get("apply_markdown") is not None),
                               mirror=request.POST.get("mirror"))

def format_updates_response(messages=[], apply_markdown=True,
                            user_profile=None, new_pointer=None,
                            mirror=None, update_types=[]):
    max_message_id = None
    if user_profile is not None:
        try:
            max_message_id = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[0].id
        except:
            pass
    if mirror is not None:
        messages = [m for m in messages if m.sending_client.name != mirror]
    ret = {'messages': [message.to_dict(apply_markdown) for message in messages],
           "result": "success",
           "msg": "",
           'server_generation': SERVER_GENERATION,
           'update_types': update_types}
    if max_message_id is not None:
        # TODO: Figure out how to accurately return this always
        ret["max_message_id"] = max_message_id
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

def return_messages_immediately(request, user_profile, client_id, **kwargs):
    last = request.POST.get("last")
    if last is None:
        # When an API user is first querying the server to subscribe,
        # there's no reason to reply immediately.
        # TODO: Make this work with server_generation/failures
        return None
    last = int(last)
    if last < 0:
        return {"msg": "Invalid 'last' argument", "result": "error"}
    # Pointer sync is disabled for now
    # client_pointer = request.POST.get("pointer")
    failures = request.POST.get("failures")
    client_server_generation = request.POST.get("server_generation")
    client_reload_pending = request.POST.get("reload_pending")

    # Pointer sync is disabled for now
    # client_wants_ptr_updates = False
    # if client_pointer is not None:
    #     client_pointer = int(client_pointer)
    #     client_wants_ptr_updates = True
    if failures is not None:
        failures = int(failures)
    if client_reload_pending is not None:
        client_reload_pending = int(client_reload_pending)

    messages = []
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
    if apply_markdown:
        for msg in response['messages']:
            if msg['content_type'] != 'text/html':
                handler.set_status(500)
                handler.finish('Internal error: bad message format')
                return
    handler.finish(response)

def get_updates_backend(request, user_profile, handler, client_id, **kwargs):
    resp = return_messages_immediately(request, user_profile,
                                       client_id, **kwargs)
    if resp is not None and resp['result'] == 'success':
        send_with_safety_check(resp, handler, **kwargs)
        return

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

@login_required_api_view
def api_get_profile(request, user_profile):
    return json_success({"pointer": user_profile.pointer,
                         "client_id": generate_client_id()})

@login_required_api_view
def api_send_message(request, user_profile):
    return send_message_backend(request, user_profile, user_profile,
                                client_name=request.POST.get("client", "API"))

@login_required_json_view
def json_send_message(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if 'time' in request.POST:
        return json_error("Invalid field 'time'")
    return send_message_backend(request, user_profile, user_profile,
                                client_name=request.POST.get("client"))

# TODO: This should have a real superuser security check
def is_super_user_api(request):
    return request.POST.get("api-key") == "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

def already_sent_mirrored_message(request):
    utc_from_ts = datetime.datetime.utcfromtimestamp
    req_time = float(request.POST['time'])
    email = request.POST['sender'].lower()
    if Message.objects.filter(sender__user__email=email,
                              content=request.POST['content'],
                              pub_date__gt=utc_from_ts(req_time - 10).replace(tzinfo=utc),
                              pub_date__lt=utc_from_ts(req_time + 10).replace(tzinfo=utc)):
        return True
    return False

# Validte that the passed in object is an email address from the user's realm
# TODO: Check that it's a real email address here.
def same_realm_email(user_profile, email):
    try:
        domain = email.split("@", 1)[1]
        return user_profile.realm.domain == domain
    except:
        return False

# Parse out the sender and huddle/personal recipients
def parse_named_users(request):
    sender = {}
    recipients = set()
    try:
        if 'sender' in request.POST:
            sender = {'email': request.POST["sender"],
                      'full_name': request.POST["fullname"],
                      'short_name': request.POST["shortname"]}

        if request.POST['type'] == 'personal':
            if ',' in request.POST['recipient']:
                # Huddle message
                for user_email in [e.strip().lower() for e in
                                   request.POST["recipient"].split(",")]:
                    recipients.add(user_email)
            else:
                user_email = request.POST["recipient"].strip().lower()
                recipients.add(user_email)
    except:
        return (False, None, None)

    return (True, sender, list(recipients))

def create_mirrored_message_users(request, user_profile):
    (valid_input, sender_data, huddle_recipients) = parse_named_users(request)
    if not valid_input:
        return (False, None)

    # First, check that the sender is in our realm:
    if 'email' in sender_data and not same_realm_email(user_profile,
                                                       sender_data['email']):
        return (False, None)
    # Then, check that all huddle/personal recipients are in our realm:
    for recipient in huddle_recipients:
        if not same_realm_email(user_profile, recipient):
            return (False, None)

    # Create a user for the sender, if needed
    if 'email' in sender_data:
        sender = create_user_if_needed(user_profile.realm, sender_data['email'],
                                       sender_data['full_name'], sender_data['short_name'],
                                       active=False)
    else:
        sender = user_profile

    # Create users for huddle/personal recipients, if needed.
    for recipient in huddle_recipients:
        create_user_if_needed(user_profile.realm, recipient,
                              recipient.split('@')[0],
                              recipient.split('@')[0],
                              active=False)

    return (True, sender)

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
def send_message_backend(request, user_profile, sender, client_name=None):
    if "type" not in request.POST:
        return json_error("Missing type")
    if "content" not in request.POST:
        return json_error("Missing message contents")
    if client_name is None:
        return json_error("Missing client")
    message_type_name = request.POST["type"]
    forged = "forged" in request.POST
    is_super_user = is_super_user_api(request)
    if forged and not is_super_user:
        return json_error("User not authorized for this query")

    if client_name == "zephyr_mirror":
        # Here's how security works for non-superuser mirroring:
        #
        # The message must be (1) a huddle/personal message (2) that
        # is both sent and received exclusively by other users in your
        # realm which (3) must be the MIT realm and (4) you must have
        # received the message.
        #
        # If that's the case, we let it through, but we still have the
        # security flaw that we're trusting your Hesiod data for users
        # you report having sent you a message.
        if "sender" not in request.POST:
            return json_error("Missing sender")
        if message_type_name != "personal" and not is_super_user:
            return json_error("User not authorized for this query")
        (valid_input, mirror_sender) = create_mirrored_message_users(request, user_profile)
        if not valid_input:
            return json_error("Invalid mirrored message")
        if user_profile.realm.domain != "mit.edu":
            return json_error("Invalid mirrored realm")
        if already_sent_mirrored_message(request):
            return json_success()
        sender = mirror_sender

    if message_type_name == 'stream':
        if "stream" not in request.POST:
            return json_error("Missing stream")
        if "subject" not in request.POST:
            return json_error("Missing subject")
        stream_name = request.POST['stream'].strip()
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
    elif message_type_name == 'personal':
        if "recipient" not in request.POST:
            return json_error("Missing recipient")
        (valid_input, _, huddle_recipients) = parse_named_users(request)
        if not valid_input:
            return json_error("Unable to parse recipients")
        if client_name == "zephyr_mirror":
            if user_profile.user.email not in huddle_recipients and not forged:
                return json_error("User not authorized for this query")

        recipient_profile_ids = set()
        for recipient in huddle_recipients:
            if recipient == "":
                continue
            try:
                recipient_profile_ids.add(UserProfile.objects.get(user__email=recipient).id)
            except UserProfile.DoesNotExist:
                return json_error("Invalid email '%s'" % (recipient))
        if len(recipient_profile_ids) > 1:
            # Make sure the sender is included in the huddle
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
    message.content = request.POST['content']
    message.recipient = recipient
    if message_type_name == 'stream':
        message.subject = subject_name
    if forged:
        # Forged messages come with a timestamp
        message.pub_date = datetime.datetime.utcfromtimestamp(float(request.POST['time'])).replace(tzinfo=utc)
    else:
        message.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
    message.sending_client = get_client(client_name)
    do_send_message(message)

    return json_success()


def validate_notify(request, handler):
    # Check the shared secret.
    # Also check the originating IP, at least for now.
    if ((request.META['REMOTE_ADDR'] not in ('127.0.0.1', '::1'))
        or (request.POST.get('secret') != settings.SHARED_SECRET)):

        handler.set_status(403)
        handler.finish('Access denied')
        return False
    return True

@asynchronous
@csrf_exempt
@require_post
def notify_new_message(request, handler):
    if not validate_notify(request, handler):
        return

    # If a message for some reason has no recipients (e.g. it is sent
    # by a bot to a stream that nobody is subscribed to), just skip
    # the message gracefully
    if request.POST["users"] == "":
        return

    # FIXME: better query
    users   = [UserProfile.objects.get(id=user)
               for user in request.POST['users'].split(',')]
    message = Message.objects.get(id=request.POST['message'])

    for user in users:
        user.receive(message)

    handler.finish()

@asynchronous
@csrf_exempt
@require_post
def notify_pointer_update(request, handler):
    if not validate_notify(request, handler):
        return

    # FIXME: better query
    user_profile = UserProfile.objects.get(id=request.POST['user'])
    new_pointer = int(request.POST['new_pointer'])
    pointer_updater = request.POST['pointer_updater']

    user_profile.update_pointer(new_pointer, pointer_updater)

    handler.finish()

@login_required_api_view
def api_get_public_streams(request, user_profile):
    streams = sorted([stream.name for stream in
                      Stream.objects.filter(realm=user_profile.realm)])
    return json_success({"streams": streams})

def gather_subscriptions(user_profile):
    subscriptions = Subscription.objects.filter(user_profile=user_profile, active=True)
    # For now, don't display the subscription for your ability to receive personals.
    return sorted([get_display_recipient(sub.recipient) for sub in subscriptions
            if sub.recipient.type == Recipient.STREAM])

@login_required_api_view
def api_get_subscriptions(request, user_profile):
    return json_success({"streams": gather_subscriptions(user_profile)})

@login_required_json_view
def json_list_subscriptions(request):
    subs = gather_subscriptions(UserProfile.objects.get(user=request.user))
    return json_success({"subscriptions": subs})

@login_required_json_view
def json_remove_subscription(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if 'subscription' not in request.POST:
        return json_error("Missing subscriptions")

    sub_name = request.POST.get('subscription')
    stream = get_stream(sub_name, user_profile.realm)
    if not stream:
        return json_error("Stream does not exist")
    did_remove = do_remove_subscription(user_profile, stream)
    if not did_remove:
        return json_error("Not subscribed, so you can't unsubscribe")

    return json_success({"data": sub_name})

def valid_stream_name(name):
    # Streams must start with a letter or number or a dot.
    return re.match(r'^[\w.][\w. -]*$', name, flags=re.UNICODE)

@login_required_api_view
def api_subscribe(request, user_profile):
    if "streams" not in request.POST:
        return json_error("Missing streams argument.")
    streams = simplejson.loads(request.POST.get("streams"))
    for stream_name in streams:
        if len(stream_name) > 30:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid characters in stream name (%s)." % (stream_name,))
    res = add_subscriptions_backend(request, user_profile, streams)
    return json_success(res)

@login_required_json_view
def json_add_subscription(request):
    user_profile = UserProfile.objects.get(user=request.user)

    if "new_subscription" not in request.POST:
        return json_error("Missing new_subscription argument")
    stream_name = request.POST.get('new_subscription').strip()
    if not valid_stream_name(stream_name):
        return json_error("Invalid characters in stream names")
    if len(stream_name) > 30:
        return json_error("Stream name %s too long." % (stream_name,))
    res = add_subscriptions_backend(request,user_profile,
                                    [request.POST["new_subscription"]])
    if len(res["already_subscribed"]) != 0:
        return json_error("Subscription already exists")
    return json_success({"data": res["subscribed"][0]})

def add_subscriptions_backend(request, user_profile, streams):
    subscribed = []
    already_subscribed = []
    for stream_name in list(set(streams)):
        stream = create_stream_if_needed(user_profile.realm, stream_name)
        did_subscribe = do_add_subscription(user_profile, stream)
        if did_subscribe:
            subscribed.append(stream_name)
        else:
            already_subscribed.append(stream_name)

    return {"subscribed": subscribed,
            "already_subscribed": already_subscribed}

@login_required_json_view
def json_change_settings(request):
    user_profile = UserProfile.objects.get(user=request.user)

    # First validate all the inputs
    if "full_name" not in request.POST:
        return json_error("Invalid settings request -- missing full_name.")
    if "new_password" not in request.POST:
        return json_error("Invalid settings request -- missing new_password.")
    if "old_password" not in request.POST:
        return json_error("Invalid settings request -- missing old_password.")
    if "confirm_password" not in request.POST:
        return json_error("Invalid settings request -- missing confirm_password.")

    old_password     = request.POST['old_password']
    new_password     = request.POST['new_password']
    confirm_password = request.POST['confirm_password']
    full_name        = request.POST['full_name']

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

@login_required_json_view
def json_stream_exists(request):
    if "stream" not in request.POST:
        return json_error("Missing stream argument.")
    stream = request.POST.get("stream")
    if not valid_stream_name(stream):
        return json_error("Invalid characters in stream name")
    exists = bool(get_stream(stream, UserProfile.objects.get(user=request.user).realm))
    return json_success({"exists": exists})

@csrf_exempt
@require_post
def api_fetch_api_key(request):
    try:
        username = request.POST['username']
        password = request.POST['password']
    except KeyError:
        return json_error("You must specify the username and password via POST.")
    user = authenticate(username=username, password=password)
    if user is None:
        return json_error("Your username or password is incorrect.", status=403)
    if not user.is_active:
        return json_error("Your account has been disabled.", status=403)
    return HttpResponse(user.userprofile.api_key)

@login_required_json_view
def json_fetch_api_key(request):
    try:
        password = request.POST['password']
    except KeyError:
        return json_error("You must specify your password to get your API key.")
    if not request.user.check_password(password):
        return json_error("Your username or password is incorrect.")
    return json_success({"api_key": request.user.userprofile.api_key})
