from django.conf import settings

def add_settings(request):
    return {
        'full_navbar':   settings.FULL_NAVBAR,
    }
