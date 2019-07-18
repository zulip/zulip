from django.conf.urls import url
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import TemplateView
import os
from django.views.static import serve
import zerver.views.development.registration
import zerver.views.auth
import zerver.views.development.email_log
import zerver.views.development.integrations

# These URLs are available only in the development environment

use_prod_static = not settings.DEBUG

urls = [
    # Serve useful development environment resources (docs, coverage reports, etc.)
    url(r'^coverage/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'var/coverage'),
                'show_indexes': True}),
    url(r'^node-coverage/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'var/node-coverage/lcov-report'),
                'show_indexes': True}),
    url(r'^casper/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'var/casper'),
                'show_indexes': True}),
    url(r'^docs/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'docs/_build/html')}),

    # The special no-password login endpoint for development
    url(r'^devlogin/$', zerver.views.auth.login_page,
        {'template_name': 'zerver/dev_login.html'}, name='zerver.views.auth.login_page'),

    # Page for testing email templates
    url(r'^emails/$', zerver.views.development.email_log.email_page),
    url(r'^emails/generate/$', zerver.views.development.email_log.generate_all_emails),
    url(r'^emails/clear/$', zerver.views.development.email_log.clear_emails),

    # Listing of useful URLs and various tools for development
    url(r'^devtools/$', TemplateView.as_view(template_name='zerver/dev_tools.html')),
    # Register New User and Realm
    url(r'^devtools/register_user/$',
        zerver.views.development.registration.register_development_user,
        name='zerver.views.development.registration.register_development_user'),
    url(r'^devtools/register_realm/$',
        zerver.views.development.registration.register_development_realm,
        name='zerver.views.development.registration.register_development_realm'),

    # Have easy access for error pages
    url(r'^errors/404/$', TemplateView.as_view(template_name='404.html')),
    url(r'^errors/5xx/$', TemplateView.as_view(template_name='500.html')),

    # Add a convinient way to generate webhook messages from fixtures.
    url(r'^devtools/integrations/$', zerver.views.development.integrations.dev_panel),
    url(r'^devtools/integrations/check_send_webhook_fixture_message$',
        zerver.views.development.integrations.check_send_webhook_fixture_message),
    url(r'^devtools/integrations/send_all_webhook_fixture_messages$',
        zerver.views.development.integrations.send_all_webhook_fixture_messages),
    url(r'^devtools/integrations/(?P<integration_name>.+)/fixtures$',
        zerver.views.development.integrations.get_fixtures),
]

# Serve static assets via the Django server
if use_prod_static:
    urls += [
        url(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
else:
    urls += staticfiles_urlpatterns()

i18n_urls = [
    url(r'^confirmation_key/$', zerver.views.development.registration.confirmation_key),
]

# These are used for voyager development. On a real voyager instance,
# these files would be served by nginx.
if settings.LOCAL_UPLOADS_DIR is not None:
    urls += [
        url(r'^user_avatars/(?P<path>.*)$', serve,
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
    ]
