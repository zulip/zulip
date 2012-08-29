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
    Recipient, get_display_recipient
from zephyr.forms import RegistrationForm

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

    zephyrs = filter_by_subscription(Zephyr.objects.all(), request.user)
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

def filter_by_subscription(zephyrs, user):
    userprofile = UserProfile.objects.get(user=user)
    subscribed_zephyrs = []
    subscriptions = [sub.recipient_id for sub in Subscription.objects.filter(userprofile_id=userprofile)]
    for zephyr in zephyrs:
        # If you are subscribed to the personal or class, or if you sent the personal, you can see the zephyr.
        if (zephyr.recipient in subscriptions) or \
                ((zephyr.sender == userprofile) and zephyr.recipient.type == "personal"):
            subscribed_zephyrs.append(zephyr)

    return subscribed_zephyrs

def get_updates(request):
    if not request.POST:
        # Do something
        pass
    last_received = request.POST.get('last_received')
    new_zephyrs = filter_by_subscription(Zephyr.objects.filter(id__gt=last_received),
                                         request.user)
    new_zephyr_list = []
    for zephyr in new_zephyrs:
        new_zephyr_list.append({"id": zephyr.id,
                                "sender": zephyr.sender.user.username,
                                "display_recipient": get_display_recipient(zephyr.recipient),
                                "instance": zephyr.instance,
                                "content": zephyr.content
                                })

    return HttpResponse(simplejson.dumps(new_zephyr_list),
                        mimetype='application/json')

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
