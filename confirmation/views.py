# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: views.py 21 2008-12-05 09:21:03Z jarek.zgoda $'


from django.shortcuts import render
from django.template import RequestContext
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from confirmation.models import Confirmation, get_object_from_key, ConfirmationKeyException, \
    render_confirmation_key_error
from zerver.models import PreregistrationUser

from typing import Any, Dict

# This is currently only used for confirming PreregistrationUser.
# Do not add other confirmation paths here.
def confirm(request, confirmation_key):
    # type: (HttpRequest, str) -> HttpResponse
    try:
        get_object_from_key(confirmation_key)
    except ConfirmationKeyException as exception:
        return render_confirmation_key_error(request, exception)

    return render(request, 'confirmation/confirm_preregistrationuser.html',
                  context={
                      'key': confirmation_key,
                      'full_name': request.GET.get("full_name", None)})
