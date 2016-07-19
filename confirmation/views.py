# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: views.py 21 2008-12-05 09:21:03Z jarek.zgoda $'


from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from confirmation.models import Confirmation
from zproject.jinja2 import render_to_response


def confirm(request, confirmation_key):
    # type: (HttpRequest, str) -> HttpResponse
    confirmation_key = confirmation_key.lower()
    obj = Confirmation.objects.confirm(confirmation_key)
    confirmed = True
    if not obj:
        # confirmation failed
        confirmed = False
        try:
            # try to get the object we was supposed to confirm
            obj = Confirmation.objects.get(confirmation_key=confirmation_key)
        except Confirmation.DoesNotExist:
            pass
    ctx = {
        'object': obj,
        'confirmed': confirmed,
        'days': getattr(settings, 'EMAIL_CONFIRMATION_DAYS', 10),
        'key': confirmation_key,
        'full_name': request.GET.get("full_name", None),
        'support_email': settings.ZULIP_ADMINISTRATOR,
        'verbose_support_offers': settings.VERBOSE_SUPPORT_OFFERS,
    }
    templates = [
        'confirmation/confirm.html',
    ]
    if obj:
        # if we have an object, we can use specific template
        templates.insert(0, 'confirmation/confirm_%s.html' % (obj._meta.model_name,))
    return render_to_response(templates, ctx, request=request)
