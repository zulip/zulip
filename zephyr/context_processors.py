from django.conf import settings

def add_settings(context):
    return { 'full_navbar': settings.FULL_NAVBAR }
