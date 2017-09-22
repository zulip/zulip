from django.conf.urls import url
from django.conf import settings
from django.views.generic import TemplateView
import os
from django.views.static import serve
import zerver.views.registration
import zerver.views.auth
import zerver.views.test_emails

# These URLs are available only in the development environment

use_prod_static = getattr(settings, 'PIPELINE_ENABLED', False)
static_root = os.path.join(settings.DEPLOY_ROOT, 'prod-static/serve' if use_prod_static else 'static')

urls = [
    # Serve static assets via the Django server
    url(r'^static/(?P<path>.*)$', serve, {'document_root': static_root}),

    # Serve useful development environment resources (docs, coverage reports, etc.)
    url(r'^coverage/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'var/coverage'),
                'show_indexes': True}),
    url(r'^node-coverage/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'var/node-coverage/lcov-report'),
                'show_indexes': True}),
    url(r'^docs/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'docs/_build/html')}),

    # The special no-password login endpoint for development
    url(r'^devlogin/$', zerver.views.auth.login_page,
        {'template_name': 'zerver/dev_login.html'}, name='zerver.views.auth.login_page'),

    # Page for testing email templates
    url(r'^emails/$', zerver.views.test_emails.email_page),

    # Listing of useful URLs and various tools for development
    url(r'^devtools/$', TemplateView.as_view(template_name='zerver/dev_tools.html')),

    # Have easy access for error pages
    url(r'^errors/404/$', TemplateView.as_view(template_name='404.html')),
    url(r'^errors/5xx/$', TemplateView.as_view(template_name='500.html')),
]

i18n_urls = [
    url(r'^confirmation_key/$', zerver.views.registration.confirmation_key),
]

# These are used for voyager development. On a real voyager instance,
# these files would be served by nginx.
if settings.LOCAL_UPLOADS_DIR is not None:
    urls += [
        url(r'^user_avatars/(?P<path>.*)$', serve,
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
    ]
