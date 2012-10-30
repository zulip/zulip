from django.conf import settings

def add_settings(request):
    return {
        'full_navbar':   settings.FULL_NAVBAR,

        # c.f. Django's STATIC_URL variable
        'static_hidden': '/static/4nrjx8cwce2bka8r/',
    }
