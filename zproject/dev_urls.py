import os
from urllib.parse import urlsplit

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.views.generic import TemplateView
from django.views.static import serve

from zerver.views.auth import config_error, login_page
from zerver.views.development.email_log import clear_emails, email_page, generate_all_emails
from zerver.views.development.integrations import (
    check_send_webhook_fixture_message,
    dev_panel,
    get_fixtures,
    send_all_webhook_fixture_messages,
)
from zerver.views.development.registration import (
    confirmation_key,
    register_development_realm,
    register_development_user,
)

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
    path('devlogin/', login_page,
         {'template_name': 'zerver/dev_login.html'}, name='login_page'),

    # Page for testing email templates
    path('emails/', email_page),
    path('emails/generate/', generate_all_emails),
    path('emails/clear/', clear_emails),

    # Listing of useful URLs and various tools for development
    path('devtools/', TemplateView.as_view(template_name='zerver/dev_tools.html')),
    # Register New User and Realm
    path('devtools/register_user/',
         register_development_user,
         name='register_dev_user'),
    path('devtools/register_realm/',
         register_development_realm,
         name='register_dev_realm'),

    # Have easy access for error pages
    path('errors/404/', TemplateView.as_view(template_name='404.html')),
    path('errors/5xx/', TemplateView.as_view(template_name='500.html')),

    # Add a convenient way to generate webhook messages from fixtures.
    path('devtools/integrations/', dev_panel),
    path('devtools/integrations/check_send_webhook_fixture_message',
         check_send_webhook_fixture_message),
    path('devtools/integrations/send_all_webhook_fixture_messages',
         send_all_webhook_fixture_messages),
    path('devtools/integrations/<integration_name>/fixtures',
         get_fixtures),

    path('config-error/<error_category_name>', config_error,
         name='config_error'),
    path('config-error/remoteuser/<error_category_name>',
         config_error),
]

# Serve static assets via the Django server
if use_prod_static:
    urls += [
        path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
    ]
else:
    def serve_static(request: HttpRequest, path: str) -> HttpResponse:
        response = staticfiles_serve(request, path)
        response["Access-Control-Allow-Origin"] = "*"
        return response

    urls += static(urlsplit(settings.STATIC_URL).path, view=serve_static)

i18n_urls = [
    path('confirmation_key/', confirmation_key),
]
urls += i18n_urls

# On a production instance, these files would be served by nginx.
if settings.LOCAL_UPLOADS_DIR is not None:
    avatars_url = path(
        'user_avatars/<path:path>',
        serve,
        {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")},
    )
    urls += [avatars_url]
