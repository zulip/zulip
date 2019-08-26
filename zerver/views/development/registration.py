from django.conf import settings
from django.http import HttpResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt

from confirmation.models import Confirmation, create_confirmation_link

from typing import Any

from zerver.models import UserProfile
from zerver.lib.response import json_success
from zerver.lib.subdomains import get_subdomain
from zerver.views.auth import create_preregistration_user
from zerver.views.registration import accounts_register


# This is used only by the casper test in 00-realm-creation.js.
def confirmation_key(request: HttpRequest) -> HttpResponse:
    return json_success(request.session.get('confirmation_key'))

def modify_postdata(request: HttpRequest, **kwargs: Any) -> None:
    request.POST._mutable = True
    for key, value in kwargs.items():
        request.POST[key] = value
    request.POST._mutable = False

@csrf_exempt
def register_development_user(request: HttpRequest) -> HttpResponse:
    if get_subdomain(request) == '':
        request.META['HTTP_HOST'] = settings.REALM_HOSTS['zulip']
    count = UserProfile.objects.count()
    name = 'user-%d' % (count,)
    email = '%s@zulip.com' % (name,)
    prereg = create_preregistration_user(email, request, realm_creation=False,
                                         password_required=False)
    activation_url = create_confirmation_link(prereg, request.get_host(),
                                              Confirmation.USER_REGISTRATION)
    key = activation_url.split('/')[-1]
    # Need to add test data to POST request as it doesnt originally contain the required parameters
    modify_postdata(request, key=key, full_name=name, password='test', terms='true')

    return accounts_register(request)

@csrf_exempt
def register_development_realm(request: HttpRequest) -> HttpResponse:
    count = UserProfile.objects.count()
    name = 'user-%d' % (count,)
    email = '%s@zulip.com' % (name,)
    realm_name = 'realm-%d' % (count,)
    prereg = create_preregistration_user(email, request, realm_creation=True,
                                         password_required=False)
    activation_url = create_confirmation_link(prereg, request.get_host(),
                                              Confirmation.REALM_CREATION)
    key = activation_url.split('/')[-1]
    # Need to add test data to POST request as it doesnt originally contain the required parameters
    modify_postdata(request, key=key, realm_name=realm_name, full_name=name, password='test',
                    realm_subdomain=realm_name, terms='true')

    return accounts_register(request)
