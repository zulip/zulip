# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: views.py 21 2008-12-05 09:21:03Z jarek.zgoda $'


from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from confirmation.models import Confirmation, get_object_from_key, ConfirmationKeyException, \
    render_confirmation_key_error

from typing import Any, Dict

def check_prereg_key_and_redirect(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    # If the key isn't valid, show the error message on the original URL
    confirmation = Confirmation.objects.filter(confirmation_key=confirmation_key).first()
    if confirmation is None or confirmation.type not in [
            Confirmation.USER_REGISTRATION, Confirmation.INVITATION, Confirmation.REALM_CREATION]:
        return render_confirmation_key_error(
            request, ConfirmationKeyException(ConfirmationKeyException.DOES_NOT_EXIST))
    try:
        get_object_from_key(confirmation_key, confirmation.type)
    except ConfirmationKeyException as exception:
        return render_confirmation_key_error(request, exception)

    # confirm_preregistrationuser.html just extracts the confirmation_key
    # (and GET parameters) and redirects to /accounts/register, so that the
    # user can enter their information on a cleaner URL.
    return render(request, 'confirmation/confirm_preregistrationuser.html',
                  context={
                      'key': confirmation_key,
                      'full_name': request.GET.get("full_name", None)})
