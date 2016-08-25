import mandrill
from django.conf import settings

MAIL_CLIENT = None

from typing import Optional

def get_mandrill_client():
    # type: () -> Optional[mandrill.Mandrill]
    if settings.MANDRILL_API_KEY is None or settings.DEVELOPMENT:
        return None

    global MAIL_CLIENT
    if not MAIL_CLIENT:
        MAIL_CLIENT = mandrill.Mandrill(settings.MANDRILL_API_KEY)

    return MAIL_CLIENT

