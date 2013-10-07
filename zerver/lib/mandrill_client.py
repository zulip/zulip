import mandrill
from django.conf import settings

MAIL_CLIENT = None

def get_mandrill_client():
    global MAIL_CLIENT
    if MAIL_CLIENT:
        return MAIL_CLIENT
    MAIL_CLIENT = mandrill.Mandrill(settings.MANDRILL_API_KEY)
    return MAIL_CLIENT

