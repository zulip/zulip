from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.shortcuts import render
from django.utils.timezone import utc

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Subscription, \
    Recipient, get_display_recipient, get_huddle, Realm, UserMessage, \
    create_user, do_send_zephyr, mit_sync_table, create_user_if_needed, \
    create_class_if_needed
from zephyr.forms import RegistrationForm

from zephyr.decorator import asynchronous

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
    return x.replace('<','&lt;').replace('>','&gt;')

def register(request):
    if request.method == 'POST':
        try:
            email = strip_html(request.POST['email'])
            company_name = email.split('@')[-1]
        except KeyError:
            company_name = None

        form = RegistrationForm(request.POST)
        if form.is_valid():
            password   = strip_html(form.cleaned_data['password'])
            full_name  = strip_html(form.cleaned_data['full_name'])
            short_name = strip_html(email.split('@')[0])
            email      = strip_html(form.cleaned_data['email'])
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
    else:
        form = RegistrationForm()
        company_name = None

    return render(request, 'zephyr/register.html', {
        'form': form, 'company_name': company_name,
    })

def accounts_home(request):
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

@login_required
@asynchronous
@require_post
def get_updates_longpoll(request, handler):
    last_received = request.POST.get('last_received')
    if not last_received:
        return json_error("Missing last_received argument")
    user_profile = UserProfile.objects.get(user=request.user)

    def on_receive(zephyrs):
        if handler.request.connection.stream.closed():
            return
        try:
            # Avoid message loop by not sending the MIT sync bot any
            # messages that we got from it in the first place.
            if request.POST.get('mit_sync_bot'):
                zephyrs = [zephyr for zephyr in zephyrs if not mit_sync_table.get(zephyr.id)]
            handler.finish({'zephyrs': [zephyr.to_dict() for zephyr in zephyrs]})
        except socket.error:
            pass

    # We need to replace this abstraction with the message list
    user_profile.add_callback(handler.async_callback(on_receive), last_received)

@login_required
@require_post
def zephyr(request):
    if 'time' in request.POST:
        return json_error("Invalid field 'time'")
    return zephyr_backend(request, request.user)

@login_required
@require_post
def forge_zephyr(request):
    email = strip_html(request.POST['sender']).lower()
    user_profile = UserProfile.objects.get(user=request.user)

    if "time" not in request.POST:
        return json_error("Missing time")

    # Create a user for the sender of the message
    user = create_user_if_needed(user_profile.realm, email, "test",
                                 strip_html(request.POST['fullname']),
                                 strip_html(request.POST['shortname']))

    # Don't send duplicate copies of forwarded messages
    if Zephyr.objects.filter(sender__user__email=email,
                             content=request.POST['new_zephyr'],
                             pub_date__gt=datetime.datetime.utcfromtimestamp(float(request.POST['time']) - 1).replace(tzinfo=utc),
                             pub_date__lt=datetime.datetime.utcfromtimestamp(float(request.POST['time']) + 1).replace(tzinfo=utc)):
        return json_success()

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

    return zephyr_backend(request, user)

@login_required
@require_post
def zephyr_backend(request, sender):
    user_profile = UserProfile.objects.get(user=request.user)
    if "type" not in request.POST:
        return json_error("Missing type")
    if "new_zephyr" not in request.POST:
        return json_error("Missing message contents")

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
        return json_error("Invalid zephyr type")

    new_zephyr = Zephyr()
    new_zephyr.sender = UserProfile.objects.get(user=sender)
    new_zephyr.content = strip_html(request.POST['new_zephyr'])
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
    do_send_zephyr(new_zephyr, synced_from_mit = 'time' in request.POST)

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
    zephyr_class = ZephyrClass.objects.get(name=sub_name, realm=user_profile.realm)
    recipient = Recipient.objects.get(type_id=zephyr_class.id,
                                      type=Recipient.CLASS)
    subscription = Subscription.objects.get(
        userprofile=user_profile, recipient=recipient)
    subscription.active = False
    subscription.save()

    return json_success({"data": sub_name})

@login_required
@require_post
def json_add_subscription(request):
    user_profile = UserProfile.objects.get(user=request.user)

    if "new_subscription" not in request.POST:
        return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

    sub_name = request.POST.get('new_subscription').strip()
    if not re.match('^[a-z A-z0-9_-]+$', sub_name):
        return json_error("Invalid characters in class names")

    zephyr_class = ZephyrClass.objects.filter(name=sub_name, realm=user_profile.realm)
    if zephyr_class:
        zephyr_class = zephyr_class[0]
        recipient = Recipient.objects.get(type_id=zephyr_class.id,
                                          type=Recipient.CLASS)
    else:
        (_, recipient) = ZephyrClass.create(sub_name, user_profile.realm)

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
    timezone         = strip_html(request.POST['timezone'])

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
    # TODO: Change the timezone
    # user_profile.timezone = timezone
    user_profile.user.save()
    user_profile.save()

    return json_success(result)

@login_required
def class_exists(request, zephyr_class):
    return HttpResponse(bool(ZephyrClass.objects.filter(name=zephyr_class)))
