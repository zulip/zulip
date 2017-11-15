# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: views.py 21 2008-12-05 09:21:03Z jarek.zgoda $'


from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from confirmation.models import Confirmation, ConfirmationKeyException, \
    get_object_from_key, render_confirmation_key_error

# This is currently only used for confirming PreregistrationUser.
# Do not add other confirmation paths here.
def confirm(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    try:
        get_object_from_key(confirmation_key, Confirmation.USER_REGISTRATION)
    except ConfirmationKeyException:
        try:
            get_object_from_key(confirmation_key, Confirmation.INVITATION)
        except ConfirmationKeyException as exception:
            return render_confirmation_key_error(request, exception)

    return render(request, 'confirmation/confirm_preregistrationuser.html',
                  context={
                      'key': confirmation_key,
                      'full_name': request.GET.get("full_name", None)})
