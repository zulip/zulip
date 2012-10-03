from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.shortcuts import render
from django.utils.timezone import utc
from django.core.exceptions import ValidationError
from django.contrib.auth.views import login as django_login_page
from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Subscription, \
    Recipient, get_display_recipient, get_huddle, Realm, \
    create_user, do_send_message, mit_sync_table, create_user_if_needed, \
    create_class_if_needed, PreregistrationUser
from zephyr.forms import RegistrationForm, HomepageForm, is_unique
from django.views.decorators.csrf import csrf_exempt

from zephyr.decorator import asynchronous
from zephyr.lib.query import last_n

from confirmation.models import Confirmation

import datetime
import simplejson
import socket
import re
import hashlib

def require_post(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.method != "POST":
            return HttpResponseBadRequest('This form can only be submitted by POST.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

# api_key_required will add the authenticated user's user_profile to
# the view function's arguments list, since we have to look it up
# anyway.
def api_key_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        # Arguably @require_post should protect us from having to do
        # this, but I don't want to count on us always getting the
        # decorator ordering right.
        if request.method != "POST":
            return HttpResponseBadRequest('This form can only be submitted by POST.')
        user_profile = UserProfile.objects.get(user__email=request.POST.get("email"))
        if user_profile is None or request.POST.get("api-key") != user_profile.api_key:
            return json_error('Invalid API user/key pair.')
        return view_func(request, user_profile, *args, **kwargs)
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

def strip_html(x):
    """Sanitize an email, class name, etc."""
    # We remove <> in order to avoid </script> within JSON embedded in HTML.
    #
    # FIXME: consider a whitelist
    return x.replace('&', '&amp;').replace('<','&lt;').replace('>','&gt;')

def get_class(class_name, realm):
    zephyr_class = ZephyrClass.objects.filter(name__iexact=class_name, realm=realm)
    if zephyr_class:
        return zephyr_class[0]
    else:
        return None

@require_post
def register(request):
    key = request.POST['key']
    email = Confirmation.objects.get(confirmation_key=key).content_object.email
    company_name = email.split('@')[-1]

    try:
        is_unique(email)
    except ValidationError:
        return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + strip_html(email))

    if request.POST.get('from_confirmation'):
        form = RegistrationForm()
    else:
        form = RegistrationForm(request.POST)
        if form.is_valid():
            password   = strip_html(form.cleaned_data['password'])
            full_name  = strip_html(form.cleaned_data['full_name'])
            short_name = strip_html(email.split('@')[0])
            domain     = strip_html(form.cleaned_data['domain'])
            realm = Realm.objects.filter(domain=domain)
            if not realm:
                realm = Realm(domain=domain)
                realm.save()
            else:
                realm = Realm.objects.get(domain=domain)
            # FIXME: sanitize email addresses
            create_user(email, password, realm, full_name, short_name)
            login(request, authenticate(username=email, password=password))
            return HttpResponseRedirect(reverse('zephyr.views.home'))

    return render(request, 'zephyr/register.html', {
        'form': form, 'company_name': company_name, 'email': email, 'key': key,
    })

def login_page(request, **kwargs):
    template_response = django_login_page(request, **kwargs)
    try:
        template_response.context_data['email'] = strip_html(request.GET['email'])
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
            return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + strip_html(email))
    return render_to_response('zephyr/accounts_home.html',
                              context_instance=RequestContext(request))

def home(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect('accounts/home/')
    user_profile = UserProfile.objects.get(user=request.user)

    zephyrs = Zephyr.objects.filter(usermessage__user_profile=user_profile)

    if user_profile.pointer == -1 and zephyrs:
        user_profile.pointer = min([zephyr.id for zephyr in zephyrs])
        user_profile.save()

    # Populate personals autocomplete list based on everyone in your
    # realm.  Later we might want a 2-layer autocomplete, where we
    # consider specially some sort of "buddy list" who e.g. you've
    # talked to before, but for small organizations, the right list is
    # everyone in your realm.
    people = [profile.user.email for profile in
              UserProfile.objects.filter(realm=user_profile.realm) if
              profile != user_profile]

    subscriptions = Subscription.objects.filter(userprofile_id=user_profile, active=True)
    classes = [get_display_recipient(sub.recipient) for sub in subscriptions
               if sub.recipient.type == Recipient.CLASS]

    return render_to_response('zephyr/index.html',
                              {'user_profile': user_profile,
                               'email_hash'  : hashlib.md5(user_profile.user.email).hexdigest(),
                               'people'      : simplejson.dumps(people),
                               'classes'     : simplejson.dumps(classes),
                               'have_initial_messages':
                                   'true' if zephyrs else 'false',
                               'show_debug':
                                   settings.DEBUG and ('show_debug' in request.GET) },
                              context_instance=RequestContext(request))

@login_required
@require_post
def update(request):
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
    return {'zephyrs': [message.to_dict(apply_markdown) for message in messages],
            'where':   where}

def return_messages_immediately(request, handler, user_profile, **kwargs):
    first = request.POST.get("first")
    last = request.POST.get("last")
    failures = request.POST.get("failures")
    if first is None or last is None:
        # When an API user is first querying the server to subscribe,
        # there's no reason to reply immediately.
        return False
    first = int(first)
    last  = int(last)
    if failures is not None:
        failures = int(failures)

    where = 'bottom'
    query = Zephyr.objects.filter(usermessage__user_profile = user_profile).order_by('id')

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

    if messages:
        handler.finish(format_updates_response(messages, where=where, **kwargs))
        return True

    if failures >= 4:
        # No messages, but still return immediately, to clear the
        # user's failures count
        handler.finish(format_updates_response([], where="bottom", **kwargs))
        return True

    return False

def get_updates_backend(request, user_profile, handler, **kwargs):
    if return_messages_immediately(request, handler, user_profile, **kwargs):
        return

    def on_receive(zephyrs):
        if handler.request.connection.stream.closed():
            return
        try:
            handler.finish(format_updates_response(zephyrs, **kwargs))
        except socket.error:
            pass

    user_profile.add_callback(handler.async_callback(on_receive))

@login_required
@asynchronous
@require_post
def get_updates(request, handler):
    if not ('last' in request.POST and 'first' in request.POST):
        return json_error("Missing message range")
    user_profile = UserProfile.objects.get(user=request.user)

    return get_updates_backend(request, user_profile, handler, apply_markdown=True)

@login_required
@asynchronous
@require_post
def get_updates_api(request, handler):
    user_profile = UserProfile.objects.get(user=request.user)
    return get_updates_backend(request, user_profile, handler,
                               apply_markdown=(request.POST.get("apply_markdown") is not None),
                               mit_sync_bot=request.POST.get("mit_sync_bot"))

# Yes, this has a name similar to the previous function.  I think this
# new name is better and expect the old function to be deleted and
# replaced by the new one soon, so I'm not going to worry about it.
@csrf_exempt
@asynchronous
@require_post
@api_key_required
def api_get_messages(request, user_profile, handler):
    return get_updates_backend(request, user_profile, handler,
                               apply_markdown=(request.POST.get("apply_markdown") is not None),
                               mit_sync_bot=request.POST.get("mit_sync_bot"))

@csrf_exempt
@require_post
@api_key_required
def api_send_message(request, user_profile):
    return zephyr_backend(request, user_profile, user_profile.user)

@login_required
@require_post
def send_message(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if 'time' in request.POST:
        return json_error("Invalid field 'time'")
    return zephyr_backend(request, user_profile, request.user)

# TODO: This should have a real superuser security check
def is_super_user_api(request):
    return request.POST.get("api-key") == "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

def already_sent_forged_message(request):
    email = strip_html(request.POST['sender']).lower()
    if Zephyr.objects.filter(sender__user__email=email,
                             content=request.POST['content'],
                             pub_date__gt=datetime.datetime.utcfromtimestamp(float(request.POST['time']) - 10).replace(tzinfo=utc),
                             pub_date__lt=datetime.datetime.utcfromtimestamp(float(request.POST['time']) + 10).replace(tzinfo=utc)):
        return True
    return False

def create_forged_message_users(request, user_profile):
    # Create a user for the sender, if needed
    email = strip_html(request.POST['sender']).lower()
    user = create_user_if_needed(user_profile.realm, email, "test",
                                 strip_html(request.POST['fullname']),
                                 strip_html(request.POST['shortname']))

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

# We do not @require_login for zephyr_backend, since it is used both
# from the API and the web service.  Code calling zephyr_backend
# should either check the API key or check that the user is logged in.
@require_post
def zephyr_backend(request, user_profile, sender):
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

    zephyr_type_name = request.POST["type"]
    if zephyr_type_name == 'class':
        if "class" not in request.POST or not request.POST["class"]:
            return json_error("Missing class")
        if "instance" not in request.POST:
            return json_error("Missing instance")

        zephyr_class = create_class_if_needed(user_profile.realm,
                                              strip_html(request.POST['class']).strip())
        recipient = Recipient.objects.get(type_id=zephyr_class.id, type=Recipient.CLASS)
    elif zephyr_type_name == 'personal':
        if "recipient" not in request.POST:
            return json_error("Missing recipient")

        recipient_data = strip_html(request.POST['recipient'])
        if ',' in recipient_data:
            # This is actually a huddle message, which shares the
            # "personal" zephyr sending form
            recipients = [r.strip() for r in recipient_data.split(',')]
            # Ignore any blank recipients
            recipients = [r for r in recipients if r]
            recipient_ids = []
            for recipient in recipients:
                try:
                    recipient_ids.append(
                        UserProfile.objects.get(user=User.objects.get(email=recipient)).id)
                except User.DoesNotExist:
                    return json_error("Invalid email '%s'" % (recipient))
            # Make sure the sender is included in the huddle
            recipient_ids.append(UserProfile.objects.get(user=request.user).id)
            huddle = get_huddle(recipient_ids)
            recipient = Recipient.objects.get(type_id=huddle.id, type=Recipient.HUDDLE)
        else:
            # This is actually a personal message
            if not User.objects.filter(email=recipient_data):
                return json_error("Invalid email")

            recipient_user = User.objects.get(email=recipient_data)
            recipient_user_profile = UserProfile.objects.get(user=recipient_user)
            recipient = Recipient.objects.get(type_id=recipient_user_profile.id,
                                              type=Recipient.PERSONAL)
    else:
        return json_error("Invalid message type")

    new_zephyr = Zephyr()
    new_zephyr.sender = UserProfile.objects.get(user=sender)
    new_zephyr.content = strip_html(request.POST['content'])
    new_zephyr.recipient = recipient
    if zephyr_type_name == 'class':
        new_zephyr.instance = strip_html(request.POST['instance'])
    if 'time' in request.POST:
        # Forged zephyrs come with a timestamp
        new_zephyr.pub_date = datetime.datetime.utcfromtimestamp(float(request.POST['time'])).replace(tzinfo=utc)
    else:
        new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)

    # To avoid message loops, we must pass whether the message was
    # synced from MIT zephyr here.
    do_send_message(new_zephyr, synced_from_mit = 'time' in request.POST)

    return json_success()

def gather_subscriptions(user_profile):
    subscriptions = Subscription.objects.filter(userprofile=user_profile, active=True)
    # For now, don't display the subscription for your ability to receive personals.
    return sorted([get_display_recipient(sub.recipient) for sub in subscriptions
            if sub.recipient.type == Recipient.CLASS])

@login_required
def subscriptions(request):
    user_profile = UserProfile.objects.get(user=request.user)

    return render_to_response('zephyr/subscriptions.html',
                              {'subscriptions': gather_subscriptions(user_profile),
                               'user_profile': user_profile},
                              context_instance=RequestContext(request))

@login_required
def json_list_subscriptions(request):
    subs = gather_subscriptions(UserProfile.objects.get(user=request.user))
    return HttpResponse(content=simplejson.dumps({"subscriptions": subs}),
                        mimetype='application/json', status=200)

@login_required
@require_post
def json_remove_subscription(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if 'subscription' not in request.POST:
        return json_error("Missing subscriptions")

    sub_name = request.POST.get('subscription')
    zephyr_class = get_class(sub_name, user_profile.realm)
    if not zephyr_class:
        return json_error("Not subscribed, so you can't unsubscribe")

    recipient = Recipient.objects.get(type_id=zephyr_class.id,
                                      type=Recipient.CLASS)
    subscription = Subscription.objects.get(
        userprofile=user_profile, recipient=recipient)
    subscription.active = False
    subscription.save()

    return json_success({"data": sub_name})

def valid_class_name(name):
    # Classes must start with a letter or number.
    return re.match('^[a-zA-Z0-9][a-z A-Z0-9_-]*$', name)

@login_required
@require_post
def json_add_subscription(request):
    user_profile = UserProfile.objects.get(user=request.user)

    if "new_subscription" not in request.POST:
        return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

    sub_name = request.POST.get('new_subscription').strip()
    if not valid_class_name(sub_name):
        return json_error("Invalid characters in class names")

    zephyr_class = create_class_if_needed(user_profile.realm, sub_name)
    recipient = Recipient.objects.get(type_id=zephyr_class.id,
                                      type=Recipient.CLASS)

    subscription = Subscription.objects.filter(userprofile=user_profile,
                                               recipient=recipient)
    if subscription:
        subscription = subscription[0]
        if not subscription.active:
            # Activating old subscription.
            subscription.active = True
            subscription.save()
            actually_new_sub = sub_name
        else:
            # Subscription already exists and is active
            return json_error("Subscription already exists")
    else:
        new_subscription = Subscription(userprofile=user_profile,
                                            recipient=recipient)
        new_subscription.save()
        actually_new_sub = sub_name
    return json_success({"data": actually_new_sub})


@login_required
def manage_settings(request):
    user_profile = UserProfile.objects.get(user=request.user)

    return render_to_response('zephyr/settings.html',
                              {'user_profile': user_profile,
                               'email_hash': hashlib.md5(user_profile.user.email).hexdigest(),
                               },
                              context_instance=RequestContext(request))

@login_required
@require_post
def change_settings(request):
    user_profile = UserProfile.objects.get(user=request.user)

    # First validate all the inputs
    if "full_name" not in request.POST:
        return json_error("Invalid settings request -- missing full_name.")
    if "short_name" not in request.POST:
        return json_error("Invalid settings request -- missing short_name.")
    if "timezone" not in request.POST:
        return json_error("Invalid settings request -- missing timezone.")
    if "new_password" not in request.POST:
        return json_error("Invalid settings request -- missing new_password.")
    if "old_password" not in request.POST:
        return json_error("Invalid settings request -- missing old_password.")
    if "confirm_password" not in request.POST:
        return json_error("Invalid settings request -- missing confirm_password.")

    old_password     = request.POST['old_password']
    new_password     = request.POST['new_password']
    confirm_password = request.POST['confirm_password']
    full_name        = strip_html(request.POST['full_name'])
    short_name       = strip_html(request.POST['short_name'])

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
    if user_profile.short_name != short_name:
        user_profile.short_name = short_name
        result['short_name'] = short_name

    user_profile.user.save()
    user_profile.save()

    return json_success(result)

@login_required
def class_exists(request, zephyr_class):
    if not valid_class_name(zephyr_class):
        return json_error("Invalid characters in class name")
    return HttpResponse(
        bool(get_class(zephyr_class,
                       UserProfile.objects.get(user=request.user).realm)))
