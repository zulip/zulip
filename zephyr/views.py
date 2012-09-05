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
    Recipient, filter_by_subscriptions, get_display_recipient, get_huddle
from zephyr.forms import RegistrationForm

import tornado.web
from zephyr.decorator import asynchronous

import datetime
import simplejson
import socket

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            u = User.objects.create_user(username=username, password=password)
            u.save()
            user = authenticate(username=username, password=password)
            login(request, user)
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
            set([get_display_recipient(zephyr.recipient) for zephyr in personals])))

    publics = filter_by_subscriptions(Zephyr.objects.filter(
        recipient__type="class").all(), request.user)
    classes = simplejson.dumps(list(
            set([get_display_recipient(zephyr.recipient) for zephyr in publics])))
    instances = simplejson.dumps(list(set(
        [zephyr.instance for zephyr in publics])))

    return render_to_response('zephyr/index.html',
                              {'zephyr_json' : zephyr_json,
                               'user_profile': user_profile,
                               'people'      : people,
                               'classes'     : classes,
                               'instances'   : instances},
                              context_instance=RequestContext(request))

@login_required
def update(request):
    if not request.POST:
        # Do something
        pass
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    if request.POST.get('pointer'):
        user_profile.pointer = request.POST.get("pointer")
        user_profile.save()
    return HttpResponse(simplejson.dumps({}), mimetype='application/json')

@asynchronous
def get_updates_longpoll(request, handler):
    if not request.POST:
        # TODO: Do something
        pass

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
def zephyr(request):
    if not request.POST:
        # TODO: Do something
        pass

    zephyr_type = request.POST["type"]
    if zephyr_type == 'class':
        class_name = request.POST['class']
        if ZephyrClass.objects.filter(name=class_name):
            my_class = ZephyrClass.objects.get(name=class_name)
        else:
            my_class = ZephyrClass()
            my_class.name = class_name
            my_class.save()
        recipient = Recipient.objects.get(type_id=my_class.id, type="class")
    elif zephyr_type == "personal":
        recipient_data = request.POST['recipient']
        if ',' in recipient_data:
            # This is actually a huddle message, which shares the
            # "personal" zephyr sending form
            recipients = [r.strip() for r in recipient_data.split(',')]
            # Ignore any blank recipients
            recipients = [r for r in recipients if r]
            recipient_ids = [UserProfile.objects.get(user=User.objects.get(username=r)).id
                             for r in recipients]
            # Include the sender in the new huddle
            recipient_ids.append(UserProfile.objects.get(user=request.user).id)
            recipient_ids = list(set(recipient_ids))
            huddle = get_huddle(recipient_ids)
            recipient = Recipient.objects.get(type_id=huddle.pk, type="huddle")
        else:
            # This is actually a personal message
            if User.objects.filter(username=recipient_data):
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
    subscriptions = Subscription.objects.filter(userprofile_id=userprofile, active=True)
    # For now, don't display the subscription for your ability to receive personals.
    sub_names = [get_display_recipient(sub.recipient_id) for sub in subscriptions if sub.recipient_id.type != "personal"]

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
        zephyr_class = ZephyrClass.objects.get(name=sub_name)
        recipient = Recipient.objects.get(type_id=zephyr_class.id, type="class")
        subscription = Subscription.objects.get(
            userprofile_id=user_profile.id, recipient_id=recipient)
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
        zephyr_class = ZephyrClass.objects.filter(name=sub_name)
        if zephyr_class:
            zephyr_class = zephyr_class[0]
        else:
            zephyr_class = ZephyrClass(name=sub_name)
            zephyr_class.save()

        recipient = Recipient.objects.filter(type_id=zephyr_class.pk, type="class")
        if recipient:
            recipient = recipient[0]
        else:
            recipient = Recipient(type_id=zephyr_class.pk, type="class")
        recipient.save()

        subscription = Subscription.objects.filter(userprofile_id=user_profile,
                                                   recipient_id=recipient)
        if subscription:
            subscription = subscription[0]
            subscription.active = True
            subscription.save()
        else:
            new_subscription = Subscription(userprofile_id=user_profile,
                                            recipient_id=recipient)
            new_subscription.save()

    return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))
