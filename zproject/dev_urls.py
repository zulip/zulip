import os
from urllib.parse import urlsplit

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.http import HttpRequest, HttpResponse
from django.urls import path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

import zerver.views.auth
import zerver.views.development.email_log
import zerver.views.development.integrations
import zerver.views.development.registration

# These URLs are available only in the development environment

use_prod_static = not settings.DEBUG

urls = [
    # Serve useful development environment resources (docs, coverage reports, etc.)
    path('coverage/<path:path>',
         serve, {'document_root':
                 os.path.join(settings.DEPLOY_ROOT, 'var/coverage'),
                 'show_indexes': True}),
    path('node-coverage/<path:path>',
         serve, {'document_root':
                 os.path.join(settings.DEPLOY_ROOT, 'var/node-coverage/lcov-report'),
                 'show_indexes': True}),
    path('docs/<path:path>',
         serve, {'document_root':
                 os.path.join(settings.DEPLOY_ROOT, 'docs/_build/html')}),

    # The special no-password login endpoint for development
    path('devlogin/', zerver.views.auth.login_page,
         {'template_name': 'zerver/dev_login.html'}, name='zerver.views.auth.login_page'),

    # Page for testing email templates
    path('emails/', zerver.views.development.email_log.email_page),
    path('emails/generate/', zerver.views.development.email_log.generate_all_emails),
    path('emails/clear/', zerver.views.development.email_log.clear_emails),

    # Listing of useful URLs and various tools for development
    path('devtools/', TemplateView.as_view(template_name='zerver/dev_tools.html')),
    # Register New User and Realm
    path('devtools/register_user/',
         zerver.views.development.registration.register_development_user,
         name='zerver.views.development.registration.register_development_user'),
    path('devtools/register_realm/',
         zerver.views.development.registration.register_development_realm,
         name='zerver.views.development.registration.register_development_realm'),

    # Have easy access for error pages
    path('errors/404/', TemplateView.as_view(template_name='404.html')),
    path('errors/5xx/', TemplateView.as_view(template_name='500.html')),

    # Add a convenient way to generate webhook messages from fixtures.
    path('devtools/integrations/', zerver.views.development.integrations.dev_panel),
    path('devtools/integrations/check_send_webhook_fixture_message',
         zerver.views.development.integrations.check_send_webhook_fixture_message),
    path('devtools/integrations/send_all_webhook_fixture_messages',
         zerver.views.development.integrations.send_all_webhook_fixture_messages),
    path('devtools/integrations/<str:integration_name>/fixtures',
         zerver.views.development.integrations.get_fixtures),
]

# Serve static assets via the Django server
if use_prod_static:
    urls += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
else:
    def serve_static(request: HttpRequest, path: str) -> HttpResponse:
        response = staticfiles_serve(request, path)
        response["Access-Control-Allow-Origin"] = "*"
        return response

    urls += static(urlsplit(settings.STATIC_URL).path, view=serve_static)

i18n_urls = [
    path('confirmation_key/', zerver.views.development.registration.confirmation_key),
]

# On a production instance, these files would be served by nginx.
if settings.LOCAL_UPLOADS_DIR is not None:
    urls += [
        re_path(r'^user_avatars/(?P<path>.*)$', serve,
                {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
    ]
