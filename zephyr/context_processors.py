from django.conf import settings

def add_settings(context):
    return {
        'full_navbar':   settings.FULL_NAVBAR,

        # c.f. Django's STATIC_URL variable
        'static_public': '/static/public/',
        'static_third':  '/static/third/',
        'static_hidden': '/static/4nrjx8cwce2bka8r/',
    }
