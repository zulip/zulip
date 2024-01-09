from django.conf import settings
from django.core.mail import send_mail
from django.core.urlresolvers import reverse


# Send mail validation to user, the email should include a link to continue the
# auth process. This is a simple example, it could easilly be extended to
# render a template and send a fancy HTML email instad.


def send_validation(strategy, backend, code):
    url = reverse('token_login', args=(code.code,))
    url = strategy.request.build_absolute_uri(url)
    send_mail('Passwordless Login', 'Use this URL to login {0}'.format(url),
              settings.EMAIL_FROM, [code.email], fail_silently=False)
