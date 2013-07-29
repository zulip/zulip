from __future__ import absolute_import

from django.conf import settings
import ujson

def add_settings(request):
    return {
        'full_navbar':   settings.FULL_NAVBAR,
    }

def add_metrics(request):
    return {
        'mixpanel_token': settings.MIXPANEL_TOKEN,
        'enable_metrics': ujson.dumps(settings.DEPLOYED),
    }
