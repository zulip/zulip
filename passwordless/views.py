from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.contrib.auth import logout as auth_logout


# Example views, most of them are just template rendering


def home(request):
    return render(request, 'home.html')


def done(request):
    return render(request, 'done.html')


def login_form(request):
    return render(request, 'form.html')


def validation_sent(request):
    return render(request, 'validation_sent.html', {
        'email': request.session['email_validation_address']
    })


def logout(request):
    auth_logout(request)
    return redirect('/')


# The user will get an email with a link pointing to this view, this view just
# redirects the user to PSA complete process for the email backend. The mail
# link could point directly to PSA view but it's handy to proxy it and do
# additional computation if needed.
def token_login(request, token):
    url = reverse('social:complete', args=('email',))
    url += '?verification_code={}'.format(token)
    return redirect(url)
