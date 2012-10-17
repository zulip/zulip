from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.shortcuts import render
from django.utils.timezone import utc
from django.core.exceptions import ValidationError
from django.contrib.auth.views import login as django_login_page
from django.contrib.auth.models import User
from zephyr.models import Message, UserProfile, Stream, Subscription, \
    Recipient, get_display_recipient, get_huddle, Realm, UserMessage, \
    create_user, do_send_message, mit_sync_table, create_user_if_needed, \
    create_stream_if_needed, PreregistrationUser
from zephyr.forms import RegistrationForm, HomepageForm, is_unique
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

SERVER_GENERATION = int(time.time())

def require_post(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.method != "POST":
            return HttpResponseBadRequest('This form can only be submitted by POST.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

# api_key_required will add the authenticated user's user_profile to
# the view function's arguments list, since we have to look it up
# anyway.
def login_required_api_view(view_func):
    @csrf_exempt
    @require_post
    def _wrapped_view_func(request, *args, **kwargs):
        # Arguably @require_post should protect us from having to do
        # this, but I don't want to count on us always getting the
        # decorator ordering right.
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
    def _wrapped_view_func(request, *args, **kwargs):
        # Arguably @require_post should protect us from having to do
        # this, but I don't want to count on us always getting the
        # decorator ordering right.
        if request.method != "POST":
            return HttpResponseBadRequest('This form can only be submitted by POST.')
        if not request.user.is_authenticated():
            return json_error("Not logged in")
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def json_response(res_type="success", msg="", data={}, status=200):
    content = {"result":res_type, "msg":msg}
    content.update(data)
    return HttpResponse(content=simplejson.dumps(content),
                        mimetype='application/json', status=status)

def json_success(data={}):
    return json_response(data=data)

def json_error(msg, data={}):
    return json_response(res_type="error", msg=msg, data=data, status=400)

def get_stream(stream_name, realm):
    stream = Stream.objects.filter(name__iexact=stream_name, realm=realm)
    if stream:
        return stream[0]
    else:
        return None

@require_post
def accounts_register(request):
    key = request.POST['key']
    email = Confirmation.objects.get(confirmation_key=key).content_object.email
    company_name = email.split('@')[-1]

    try:
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
            domain     = form.cleaned_data['domain']

            try:
                realm = Realm.objects.get(domain=domain)
            except Realm.DoesNotExist:
                realm = Realm(domain=domain)
                realm.save()

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

def home(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse(settings.NOT_LOGGED_IN_REDIRECT))
    user_profile = UserProfile.objects.get(user=request.user)

    num_messages = UserMessage.objects.filter(user_profile=user_profile).count()

    if user_profile.pointer == -1 and num_messages > 0:
        min_id = UserMessage.objects.filter(user_profile=user_profile).order_by("message")[0].message_id
        user_profile.pointer = min_id
        user_profile.save()

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

    subscriptions = Subscription.objects.select_related().filter(userprofile_id=user_profile, active=True)
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
                                   settings.DEBUG and ('show_debug' in request.GET),
                               'server_generation': SERVER_GENERATION},
                              context_instance=RequestContext(request))

@login_required_json_view
def json_update_pointer(request):
    user_profile = UserProfile.objects.get(user=request.user)
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
    user_profile.save()
    return json_success()

def format_updates_response(messages, mit_sync_bot=False, apply_markdown=False, where='bottom'):
    if mit_sync_bot:
        messages = [m for m in messages if not mit_sync_table.get(m.id)]
    return {'messages': [message.to_dict(apply_markdown) for message in messages],
            "result": "success",
            "msg": "",
            'where':   where,
            'server_generation': SERVER_GENERATION}

def return_messages_immediately(request, handler, user_profile, **kwargs):
    first = request.POST.get("first")
    last = request.POST.get("last")
    failures = request.POST.get("failures")
    client_server_generation = request.POST.get("server_generation")
    client_reload_pending = request.POST.get("reload_pending")
    if first is None or last is None:
        # When an API user is first querying the server to subscribe,
        # there's no reason to reply immediately.
        return False
    first = int(first)
    last  = int(last)
    if failures is not None:
        failures = int(failures)

    where = 'bottom'
    query = Message.objects.select_related().filter(usermessage__user_profile = user_profile).order_by('id')

    if last == -1:
        # User has no messages yet
        # Get a range around the pointer
        ptr = user_profile.pointer
        messages = (last_n(200, query.filter(id__lt=ptr))
                  + list(query.filter(id__gte=ptr)[:200]))
    else:
        messages = query.filter(id__gt=last)[:400]
        if not messages:
            # No more messages in the future; try filling in from the past.
            messages = last_n(400, query.filter(id__lt=first))
            where = 'top'

    # Filter for mit_sync_bot before checking whether there are any
    # messages to pass on.  If we don't do this, when the only message
    # to forward is one that was sent via mit_sync_bot, the API client
    # will end up in an endless loop requesting more data from us.
    if kwargs.get("mit_sync_bot"):
        messages = [m for m in messages if not mit_sync_table.get(m.id)]

    if messages:
        handler.finish(format_updates_response(messages, where=where, **kwargs))
        return True

    if failures >= 4:
        # No messages, but still return immediately, to clear the
        # user's failures count
        handler.finish(format_updates_response([], where="bottom", **kwargs))
        return True

    if (client_server_generation is not None
        and int(client_server_generation) != SERVER_GENERATION
        and not client_reload_pending):
        # No messages, but still return immediately to inform the
        # client that they should reload
        handler.finish(format_updates_response([], where="bottom", **kwargs))
        return True

    return False

def get_updates_backend(request, user_profile, handler, **kwargs):
    if return_messages_immediately(request, handler, user_profile, **kwargs):
        return

    def on_receive(messages):
        if handler.request.connection.stream.closed():
            return
        try:
            handler.finish(format_updates_response(messages, **kwargs))
        except socket.error:
            pass

    user_profile.add_callback(handler.async_callback(on_receive))

@asynchronous
@login_required_json_view
def json_get_updates(request, handler):
    if not ('last' in request.POST and 'first' in request.POST):
        return json_error("Missing message range")
    user_profile = UserProfile.objects.get(user=request.user)

    return get_updates_backend(request, user_profile, handler, apply_markdown=True)

@asynchronous
@login_required_api_view
def api_get_messages(request, user_profile, handler):
    return get_updates_backend(request, user_profile, handler,
                               apply_markdown=(request.POST.get("apply_markdown") is not None),
                               mit_sync_bot=request.POST.get("mit_sync_bot"))

@login_required_api_view
def api_send_message(request, user_profile):
    return send_message_backend(request, user_profile, user_profile.user)

@login_required_json_view
def json_send_message(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if 'time' in request.POST:
        return json_error("Invalid field 'time'")
    return send_message_backend(request, user_profile, request.user)

# TODO: This should have a real superuser security check
def is_super_user_api(request):
    return request.POST.get("api-key") == "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

def already_sent_forged_message(request):
    email = request.POST['sender'].lower()
    if Message.objects.filter(sender__user__email=email,
                              content=request.POST['content'],
                              pub_date__gt=datetime.datetime.utcfromtimestamp(float(request.POST['time']) - 10).replace(tzinfo=utc),
                              pub_date__lt=datetime.datetime.utcfromtimestamp(float(request.POST['time']) + 10).replace(tzinfo=utc)):
        return True
    return False

def create_forged_message_users(request, user_profile):
    # Create a user for the sender, if needed
    email = request.POST['sender'].lower()
    user = create_user_if_needed(user_profile.realm, email, "test",
                                 request.POST['fullname'],
                                 request.POST['shortname'])

    # Create users for huddle recipients, if needed.
    if request.POST['type'] == 'personal':
        if ',' in request.POST['recipient']:
            # Huddle message
            for user_email in [e.strip() for e in request.POST["recipient"].split(",")]:
                create_user_if_needed(user_profile.realm, user_email, "test",
                                      user_email.split('@')[0],
                                      user_email.split('@')[0])
        else:
            user_email = request.POST["recipient"].strip()
            create_user_if_needed(user_profile.realm, user_email, "test",
                                  user_email.split('@')[0],
                                  user_email.split('@')[0])
    return user

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
def send_message_backend(request, user_profile, sender):
    if "type" not in request.POST:
        return json_error("Missing type")
    if "content" not in request.POST:
        return json_error("Missing message contents")
    if "forged" in request.POST:
        if not is_super_user_api(request):
            return json_error("User not authorized for this query")
        if "time" not in request.POST:
            return json_error("Missing time")
        if already_sent_forged_message(request):
            return json_success()
        sender = create_forged_message_users(request, user_profile)

    message_type_name = request.POST["type"]
    if message_type_name == 'stream':
        if "stream" not in request.POST:
            return json_error("Missing stream")
        if "subject" not in request.POST:
            return json_error("Missing subject")
        stream_name = request.POST['stream'].strip()
        subject_name = request.POST['subject'].strip()

        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name")
        ## FIXME: Commented out temporarily while we figure out what we want
        # if not valid_stream_name(subject_name):
        #     return json_error("Invalid subject name")

        stream = create_stream_if_needed(user_profile.realm, stream_name)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    elif message_type_name == 'personal':
        if "recipient" not in request.POST:
            return json_error("Missing recipient")

        recipient_data = request.POST['recipient']
        if ',' in recipient_data:
            # This is actually a huddle message, which shares the
            # "personal" message sending form
            recipients = [r.strip() for r in recipient_data.split(',')]
            # Ignore any blank recipients
            recipients = [r for r in recipients if r]
            recipient_ids = []
            for recipient in recipients:
                try:
                    recipient_ids.append(
                        UserProfile.objects.get(user__email=recipient).id)
                except UserProfile.DoesNotExist:
                    return json_error("Invalid email '%s'" % (recipient))
            # Make sure the sender is included in the huddle
            recipient_ids.append(UserProfile.objects.get(user=sender).id)
            huddle = get_huddle(recipient_ids)
            recipient = Recipient.objects.get(type_id=huddle.id, type=Recipient.HUDDLE)
        else:
            # This is actually a personal message
            if not User.objects.filter(email=recipient_data):
                return json_error("Invalid email '%s'" % (recipient_data))

            recipient_user = User.objects.get(email=recipient_data)
            recipient_user_profile = UserProfile.objects.get(user=recipient_user)
            recipient = Recipient.objects.get(type_id=recipient_user_profile.id,
                                              type=Recipient.PERSONAL)
    else:
        return json_error("Invalid message type")

    message = Message()
    message.sender = UserProfile.objects.get(user=sender)
    message.content = request.POST['content']
    message.recipient = recipient
    if message_type_name == 'stream':
        message.subject = subject_name
    if 'time' in request.POST:
        # Forged messages come with a timestamp
        message.pub_date = datetime.datetime.utcfromtimestamp(float(request.POST['time'])).replace(tzinfo=utc)
    else:
        message.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)

    # To avoid message loops, we must pass whether the message was
    # synced from MIT message here.
    do_send_message(message, synced_from_mit = 'time' in request.POST)

    return json_success()


@login_required_api_view
def api_get_public_streams(request, user_profile):
    streams = sorted([stream.name for stream in
                      Stream.objects.filter(realm=user_profile.realm)])
    return json_success({"streams": streams})

def gather_subscriptions(user_profile):
    subscriptions = Subscription.objects.filter(userprofile=user_profile, active=True)
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
        return json_error("Not subscribed, so you can't unsubscribe")

    recipient = Recipient.objects.get(type_id=stream.id,
                                      type=Recipient.STREAM)
    subscription = Subscription.objects.get(
        userprofile=user_profile, recipient=recipient)
    subscription.active = False
    subscription.save()

    return json_success({"data": sub_name})

def valid_stream_name(name):
    # Streams must start with a letter or number.
    return re.match("^[.a-zA-Z0-9][.a-z A-Z0-9_-]*$", name)

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
    for stream_name in streams:
        stream = create_stream_if_needed(user_profile.realm, stream_name)
        recipient = Recipient.objects.get(type_id=stream.id,
                                          type=Recipient.STREAM)

        try:
            subscription = Subscription.objects.get(userprofile=user_profile,
                                                    recipient=recipient)
            if subscription.active:
                # Subscription already exists and is active
                already_subscribed.append(stream_name)
                continue
        except Subscription.DoesNotExist:
            subscription = Subscription(userprofile=user_profile,
                                        recipient=recipient)
        subscription.active = True
        subscription.save()
        subscribed.append(stream_name)

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
        user_profile.user.set_password(new_password)

    result = {}
    if user_profile.full_name != full_name:
        user_profile.full_name = full_name
        result['full_name'] = full_name

    user_profile.user.save()
    user_profile.save()

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
        return HttpResponseBadRequest("You must specify the username and password via POST.")
    user = authenticate(username=username, password=password)
    if user is None:
        return HttpResponseForbidden("Your username or password is incorrect.")
    if not user.is_active:
        return HttpResponseForbidden("Your account has been disabled.")
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
