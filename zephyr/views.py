from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.shortcuts import render
from django.utils.timezone import utc

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Subscription, \
    Recipient, filter_by_subscriptions, get_display_recipient, get_huddle, \
    create_user_profile, Realm
from zephyr.forms import RegistrationForm

import tornado.web
from zephyr.decorator import asynchronous

import datetime
import simplejson
import socket

def require_post(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.method != "POST":
            return HttpResponseBadRequest('This form can only be submitted by POST.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def json_response(res_type="success", msg="", status=200):
    return HttpResponse(content=simplejson.dumps({"result":res_type, "msg":msg}),
                        mimetype='application/json', status=status)

def json_success():
    return json_response()

def json_error(msg):
    return json_response(res_type="error", msg=msg, status=400)

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            domain = request.POST['domain']
            realm = Realm.objects.filter(domain=domain)
            if not realm:
                realm = Realm(domain=domain)
            else:
                realm = Realm.objects.get(domain=domain)
            user = User.objects.create_user(username=username, password=password)
            user.save()
            create_user_profile(user, realm)
            login(request, authenticate(username=username, password=password))
            return HttpResponseRedirect(reverse('zephyr.views.home'))
    else:
        form = RegistrationForm()

    return render(request, 'zephyr/register.html', {
        'form': form,
    })

def accounts_home(request):
    return render_to_response('zephyr/accounts_home.html',
                              context_instance=RequestContext(request))

def home(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect('accounts/home/')

    zephyrs = filter_by_subscriptions(Zephyr.objects.all(), request.user)

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    if user_profile.pointer == -1 and zephyrs:
        user_profile.pointer = min([zephyr.id for zephyr in zephyrs])
        user_profile.save()
    zephyr_json = simplejson.dumps([zephyr.to_dict() for zephyr in zephyrs])

    personals = filter_by_subscriptions(Zephyr.objects.filter(
        recipient__type="personal").all(), request.user)
    people = simplejson.dumps(list(
            set(get_display_recipient(zephyr.recipient) for zephyr in personals)))

    publics = filter_by_subscriptions(Zephyr.objects.filter(
        recipient__type="class").all(), request.user)

    subscriptions = Subscription.objects.filter(userprofile_id=user_profile, active=True)
    classes = simplejson.dumps([get_display_recipient(sub.recipient) for sub in subscriptions
                                     if sub.recipient.type == "class"])

    instances = simplejson.dumps(list(
            set(zephyr.instance for zephyr in publics)))

    return render_to_response('zephyr/index.html',
                              {'zephyr_json' : zephyr_json,
                               'user_profile': user_profile,
                               'people'      : people,
                               'classes'     : classes,
                               'instances'   : instances},
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

@asynchronous
@require_post
def get_updates_longpoll(request, handler):
    last_received = request.POST.get('last_received')
    if not last_received:
        # TODO: return error?
        pass

    user = request.user
    user_profile = UserProfile.objects.get(user=user)

    def on_receive(zephyrs):
        if handler.request.connection.stream.closed():
            return
        try:
            handler.finish({'zephyrs': [zephyr.to_dict() for zephyr in zephyrs]})
        except socket.error, e:
            pass

    # We need to replace this abstraction with the message list
    user_profile.add_callback(handler.async_callback(on_receive), last_received)

@login_required
@require_post
def zephyr(request):
    user_profile = UserProfile.objects.get(user=request.user)
    zephyr_type = request.POST["type"]
    if zephyr_type == 'class':
        class_name = request.POST['class']
        if ZephyrClass.objects.filter(name=class_name, realm=user_profile.realm):
            my_class = ZephyrClass.objects.get(name=class_name, realm=user_profile.realm)
        else:
            my_class = ZephyrClass()
            my_class.name = class_name
            my_class.realm = user_profile.realm
            my_class.save()
            recipient = Recipient(type_id=my_class.id, type="class")
            recipient.save()
        try:
            recipient = Recipient.objects.get(type_id=my_class.id, type="class")
        except Recipient.DoesNotExist:
            return json_error("Invalid class")
    elif zephyr_type == "personal":
        recipient_data = request.POST['recipient']
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
                        UserProfile.objects.get(user=User.objects.get(username=recipient)).id)
                except User.DoesNotExist, e:
                    return json_error("Invalid username '%s'" % (recipient))
            # Make sure the sender is included in the huddle
            recipient_ids.append(UserProfile.objects.get(user=request.user).id)
            huddle = get_huddle(recipient_ids)
            recipient = Recipient.objects.get(type_id=huddle.pk, type="huddle")
        else:
            # This is actually a personal message
            if not User.objects.filter(username=recipient_data):
                return json_error("Invalid username")

            recipient_user = User.objects.get(username=recipient_data)
            recipient_user_profile = UserProfile.objects.get(user=recipient_user)
            recipient = Recipient.objects.get(type_id=recipient_user_profile.id, type="personal")
    else:
        # Do something smarter here
        raise

    new_zephyr = Zephyr()
    new_zephyr.sender = UserProfile.objects.get(user=request.user)
    new_zephyr.content = request.POST['new_zephyr']
    new_zephyr.recipient = recipient
    if zephyr_type == "class":
        new_zephyr.instance = request.POST['instance']
    new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
    new_zephyr.save()

    return HttpResponse('')

@login_required
def subscriptions(request):
    userprofile = UserProfile.objects.get(user=request.user)
    subscriptions = Subscription.objects.filter(userprofile=userprofile, active=True)
    # For now, don't display the subscription for your ability to receive personals.
    sub_names = [get_display_recipient(sub.recipient) for sub in subscriptions
                 if sub.recipient.type == "class"]

    return render_to_response('zephyr/subscriptions.html',
                              {'subscriptions': sub_names, 'user_profile': userprofile},
                              context_instance=RequestContext(request))

@login_required
def manage_subscriptions(request):
    if not request.POST:
        # Do something reasonable.
        return
    user_profile = UserProfile.objects.get(user=request.user)

    unsubs = request.POST.getlist('subscription')
    for sub_name in unsubs:
        zephyr_class = ZephyrClass.objects.get(name=sub_name, realm=user_profile.realm)
        recipient = Recipient.objects.get(type_id=zephyr_class.id, type="class")
        subscription = Subscription.objects.get(
            userprofile=user_profile, recipient=recipient)
        subscription.active = False
        subscription.save()

    return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

@login_required
def add_subscriptions(request):
    if not request.POST:
        # Do something reasonable.
        return
    user_profile = UserProfile.objects.get(user=request.user)

    new_subs = request.POST.get('new_subscriptions')
    if not new_subs:
        return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

    for sub_name in new_subs.split(","):
        zephyr_class = ZephyrClass.objects.filter(name=sub_name, realm=user_profile.realm)
        if zephyr_class:
            zephyr_class = zephyr_class[0]
        else:
            zephyr_class = ZephyrClass(name=sub_name, realm=user_profile.realm)
            zephyr_class.save()

        recipient = Recipient.objects.filter(type_id=zephyr_class.pk, type="class")
        if recipient:
            recipient = recipient[0]
        else:
            recipient = Recipient(type_id=zephyr_class.pk, type="class")
        recipient.save()

        subscription = Subscription.objects.filter(userprofile=user_profile,
                                                   recipient=recipient)
        if subscription:
            subscription = subscription[0]
            subscription.active = True
            subscription.save()
        else:
            new_subscription = Subscription(userprofile=user_profile,
                                            recipient=recipient)
            new_subscription.save()

    return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

@login_required
def class_exists(request, zephyr_class):
    return HttpResponse(bool(ZephyrClass.objects.filter(name=zephyr_class)))
