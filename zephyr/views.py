from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.shortcuts import render
from django.utils.timezone import utc

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Recipient, get_display_recipient, filter_by_subscriptions
from zephyr.forms import RegistrationForm

import tornado.web
from zephyr.decorator import asynchronous

import datetime
import simplejson

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
    for zephyr in zephyrs:
        zephyr.display_recipient = get_display_recipient(zephyr.recipient)

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    if user_profile.pointer == -1 and zephyrs:
        user_profile.pointer = min([zephyr.id for zephyr in zephyrs])
        user_profile.save()
    return render_to_response('zephyr/index.html', {'zephyrs': zephyrs, 'user_profile': user_profile},
                              context_instance=RequestContext(request))

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
        new_zephyr_list = []
        for zephyr in zephyrs:
            new_zephyr_list.append({"id": zephyr.id,
                                    "sender": zephyr.sender.user.username,
                                    "display_recipient": get_display_recipient(zephyr.recipient),
                                    "type": zephyr.recipient.type,
                                    "instance": zephyr.instance,
                                    "content": zephyr.content
                                    })
        try:
            handler.finish({'zephyrs': new_zephyr_list})
        except socket.error, e:
            pass

    # We need to replace this abstraction with the message list
    user_profile.add_callback(handler.async_callback(on_receive), last_received)

@login_required
def personal_zephyr(request):
    username = request.POST['recipient']
    if User.objects.filter(username=username):
        user = User.objects.get(username=username)
    else:
        # Do something reasonable.
        return HttpResponseRedirect(reverse('zephyr.views.home'))

    # Right now, you can't make recipients on the fly by sending zephyrs to new
    # classes or people.
    user_profile = UserProfile.objects.get(user=user)
    recipient = Recipient.objects.get(user_or_class=user_profile.id, type="personal")

    new_zephyr = Zephyr()
    new_zephyr.sender = UserProfile.objects.get(user=request.user)
    new_zephyr.content = request.POST['new_personal_zephyr']
    new_zephyr.recipient = recipient
    new_zephyr.instance = u''
    new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
    new_zephyr.save()

    return HttpResponseRedirect(reverse('zephyr.views.home'))

@login_required
def zephyr(request):
    class_name = request.POST['class']
    if ZephyrClass.objects.filter(name=class_name):
        my_class = ZephyrClass.objects.get(name=class_name)
    else:
        my_class = ZephyrClass()
        my_class.name = class_name
        my_class.save()

    # Right now, you can't make recipients on the fly by sending zephyrs to new
    # classes or people.
    recipient = Recipient.objects.get(user_or_class=my_class.id, type="class")

    new_zephyr = Zephyr()
    new_zephyr.sender = UserProfile.objects.get(user=request.user)
    new_zephyr.content = request.POST['new_zephyr']
    new_zephyr.recipient = recipient
    new_zephyr.instance = request.POST['instance']
    new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
    new_zephyr.save()

    return HttpResponseRedirect(reverse('zephyr.views.home'))
