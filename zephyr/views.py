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
    Recipient, get_display_recipient, get_huddle, \
    create_user_profile, Realm, UserMessage, create_zephyr_class
from zephyr.forms import RegistrationForm

from zephyr.decorator import asynchronous

import datetime
import simplejson
import socket
import re

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
            full_name = request.POST['full_name']
            short_name = request.POST['short_name']
            email = request.POST['email']
            domain = request.POST['domain']
            realm = Realm.objects.filter(domain=domain)
            if not realm:
                realm = Realm(domain=domain)
                realm.save()
            else:
                realm = Realm.objects.get(domain=domain)
            user = User.objects.create_user(username=username, password=password, email=email)
            user.save()
            create_user_profile(user, realm, full_name, short_name)
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
    user_profile = UserProfile.objects.get(user=request.user)

    zephyrs = [um.message for um in
               UserMessage.objects.filter(user_profile=user_profile)]

    if user_profile.pointer == -1 and zephyrs:
        user_profile.pointer = min([zephyr.id for zephyr in zephyrs])
        user_profile.save()

    zephyr_json = simplejson.dumps([zephyr.to_dict() for zephyr in zephyrs])

    # Populate personals autocomplete list based on everyone in your
    # realm.  Later we might want a 2-layer autocomplete, where we
    # consider specially some sort of "buddy list" who e.g. you've
    # talked to before, but for small organizations, the right list is
    # everyone in your realm.
    people = [profile.user.username for profile in
              UserProfile.objects.filter(realm=user_profile.realm) if
              profile != user_profile]

    subscriptions = Subscription.objects.filter(userprofile_id=user_profile, active=True)
    classes = [get_display_recipient(sub.recipient) for sub in subscriptions
               if sub.recipient.type == Recipient.CLASS]

    instances = list(set([zephyr.instance for zephyr in zephyrs
                          if zephyr.recipient.type == Recipient.CLASS]))

    return render_to_response('zephyr/index.html',
                              {'zephyr_array' : zephyr_json,
                               'user_profile': user_profile,
                               'people'      : simplejson.dumps(people),
                               'classes'     : simplejson.dumps(classes),
                               'instances'   : simplejson.dumps(instances)},
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
            handler.finish({'zephyrs': [zephyr.to_dict() for zephyr in zephyrs]})
        except socket.error:
            pass

    # We need to replace this abstraction with the message list
    user_profile.add_callback(handler.async_callback(on_receive), last_received)

@login_required
@require_post
def zephyr(request):
    return zephyr_backend(request, request.user)

@login_required
@require_post
def forge_zephyr(request):
    username = request.POST['sender']
    user_profile = UserProfile.objects.get(user=request.user)
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # forge a user for this person
        user = User.objects.create_user(username=username, password="test",
                                        email=(username if '@' in username else ''))
        user.save()
        create_user_profile(user, user_profile.realm,
                            request.POST['fullname'], request.POST['shortname'])
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

        class_name = request.POST['class'].strip()
        if ZephyrClass.objects.filter(name=class_name, realm=user_profile.realm):
            my_class = ZephyrClass.objects.get(name=class_name, realm=user_profile.realm)
        else:
            my_class = ZephyrClass()
            my_class.name = class_name
            my_class.realm = user_profile.realm
            my_class.save()
            recipient = Recipient(type_id=my_class.id, type=Recipient.CLASS)
            recipient.save()
        try:
            recipient = Recipient.objects.get(type_id=my_class.id, type=Recipient.CLASS)
        except Recipient.DoesNotExist:
            return json_error("Invalid class")
    elif zephyr_type_name == 'personal':
        if "recipient" not in request.POST:
            return json_error("Missing recipient")

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
                except User.DoesNotExist:
                    return json_error("Invalid username '%s'" % (recipient))
            # Make sure the sender is included in the huddle
            recipient_ids.append(UserProfile.objects.get(user=request.user).id)
            huddle = get_huddle(recipient_ids)
            recipient = Recipient.objects.get(type_id=huddle.id, type=Recipient.HUDDLE)
        else:
            # This is actually a personal message
            if not User.objects.filter(username=recipient_data):
                return json_error("Invalid username")

            recipient_user = User.objects.get(username=recipient_data)
            recipient_user_profile = UserProfile.objects.get(user=recipient_user)
            recipient = Recipient.objects.get(type_id=recipient_user_profile.id,
                                              type=Recipient.PERSONAL)
    else:
        return json_error("Invalid zephyr type")

    new_zephyr = Zephyr()
    new_zephyr.sender = UserProfile.objects.get(user=sender)
    new_zephyr.content = request.POST['new_zephyr']
    new_zephyr.recipient = recipient
    if zephyr_type_name == 'class':
        new_zephyr.instance = request.POST['instance']
    new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
    new_zephyr.save()

    return json_success()

@login_required
def subscriptions(request):
    userprofile = UserProfile.objects.get(user=request.user)
    subscriptions = Subscription.objects.filter(userprofile=userprofile, active=True)
    # For now, don't display the subscription for your ability to receive personals.
    sub_names = [get_display_recipient(sub.recipient) for sub in subscriptions
                 if sub.recipient.type == Recipient.CLASS]

    return render_to_response('zephyr/subscriptions.html',
                              {'subscriptions': sub_names, 'user_profile': userprofile},
                              context_instance=RequestContext(request))

@login_required
@require_post
def manage_subscriptions(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if 'subscription' not in request.POST:
        return json_error("Missing subscriptions")

    unsubs = request.POST.getlist('subscription')
    for sub_name in unsubs:
        zephyr_class = ZephyrClass.objects.get(name=sub_name, realm=user_profile.realm)
        recipient = Recipient.objects.get(type_id=zephyr_class.id,
                                          type=Recipient.CLASS)
        subscription = Subscription.objects.get(
            userprofile=user_profile, recipient=recipient)
        subscription.active = False
        subscription.save()

    return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

@login_required
@require_post
def add_subscriptions(request):
    user_profile = UserProfile.objects.get(user=request.user)

    if "new_subscriptions" not in request.POST:
        return HttpResponseRedirect(reverse('zephyr.views.subscriptions'))

    new_subs = [s.strip() for s in
                request.POST.get('new_subscriptions').split(",")]
    for sub_name in new_subs:
        if not re.match('^[a-zA-z0-9_-]+$', sub_name):
            return json_error("Invalid characters in class names")

    for sub_name in new_subs:
        zephyr_class = ZephyrClass.objects.filter(name=sub_name, realm=user_profile.realm)
        if zephyr_class:
            zephyr_class = zephyr_class[0]
            recipient = Recipient.objects.get(type_id=zephyr_class.id,
                                              type=Recipient.CLASS)
        else:
            (_, recipient) = create_zephyr_class(sub_name, user_profile.realm)

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
