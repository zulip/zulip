import os
from urllib.parse import urlsplit

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.http.request import HttpRequest
from django.http.response import FileResponse, HttpResponse
from django.urls import path
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve

from zerver.views.auth import login_page
from zerver.views.development.cache import remove_caches
from zerver.views.development.camo import handle_camo_url
from zerver.views.development.dev_login import (
    api_dev_fetch_api_key,
    api_dev_list_users,
    dev_direct_login,
)
from zerver.views.development.email_log import clear_emails, email_page, generate_all_emails
from zerver.views.development.help import help_dev_mode_view
from zerver.views.development.integrations import (
    check_send_webhook_fixture_message,
    dev_panel,
    get_fixtures,
    send_all_webhook_fixture_messages,
)
from zerver.views.development.registration import (
    confirmation_key,
    register_demo_development_realm,
    register_development_realm,
    register_development_user,
)
from zerver.views.development.showroom import (
    showroom_component_banners,
    showroom_component_buttons,
    showroom_component_inputs,
)
from zerver.views.errors import config_error

# These URLs are available only in the development environment

use_prod_static = not settings.DEBUG

# Every error page template, grouped by what the user can do next (each
# group shares an illustration), so each can be viewed at
# /errors/<slug>/ and together at /devtools/error_pages/. The context
# fills in values that the real views compute per request.
DEV_ERROR_PAGE_GROUPS: list[tuple[str, list[tuple[str, str, dict[str, object]]]]] = [
    (
        "Not found",
        [
            ("404", "404.html", {}),
            ("link-does-not-exist", "confirmation/link_does_not_exist.html", {}),
            ("link-malformed", "confirmation/link_malformed.html", {}),
        ],
    ),
    (
        "Expired",
        [
            ("link-expired", "confirmation/link_expired.html", {}),
            (
                "realm-creation-link-invalid",
                "zerver/portico_error_pages/realm_creation_link_invalid.html",
                {},
            ),
            ("user-deactivated", "zerver/portico_error_pages/user_deactivated.html", {}),
        ],
    ),
    (
        "No access",
        [
            ("403", "4xx.html", {"csrf_failure": True}),
            ("auth-subdomain", "zerver/portico_error_pages/auth_subdomain.html", {}),
            (
                "realm-creation-disabled",
                "zerver/portico_error_pages/realm_creation_disabled.html",
                {},
            ),
            (
                "demo-creation-disabled",
                "zerver/portico_error_pages/demo_creation_disabled.html",
                {},
            ),
        ],
    ),
    (
        "Rate limit",
        [
            (
                "rate-limit-exceeded",
                "zerver/portico_error_pages/rate_limit_exceeded.html",
                {"retry_after_string": "5 minutes"},
            ),
            (
                "remote-server-rate-limit-exceeded",
                "corporate/billing/remote_server_rate_limit_exceeded.html",
                {"retry_after_string": "5 minutes"},
            ),
        ],
    ),
    (
        "Update needed",
        [
            (
                "unsupported-browser",
                "zerver/portico_error_pages/unsupported_browser.html",
                {"browser_name": "Internet Explorer"},
            ),
            (
                "insecure-desktop-app",
                "zerver/portico_error_pages/insecure_desktop_app.html",
                {},
            ),
        ],
    ),
    (
        "Server error",
        [
            ("5xx", "500.html", {}),
            ("405", "4xx.html", {"status_code": 405}),
        ],
    ),
    (
        "Self-hosted",
        [
            (
                "remote-realm-server-mismatch",
                "zerver/portico_error_pages/remote_realm_server_mismatch_error.html",
                {},
            ),
            (
                "remote-realm-login-error",
                "corporate/billing/remote_realm_login_error_for_server_on_active_plan.html",
                {"server_plan_name": "Zulip Business"},
            ),
            (
                "remote-server-login-error",
                "corporate/billing/remote_server_login_error_for_any_realm_on_active_plan.html",
                {},
            ),
        ],
    ),
]

urls = [
    # Serve useful development environment resources (docs, coverage reports, etc.)
    path(
        "coverage/<path:path>",
        serve,
        {"document_root": os.path.join(settings.DEPLOY_ROOT, "var/coverage"), "show_indexes": True},
    ),
    path(
        "node-coverage/<path:path>",
        serve,
        {
            "document_root": os.path.join(settings.DEPLOY_ROOT, "var/node-coverage/lcov-report"),
            "show_indexes": True,
        },
    ),
    path("docs/", RedirectView.as_view(url="/docs/index.html")),
    path(
        "docs/<path:path>",
        serve,
        {"document_root": os.path.join(settings.DEPLOY_ROOT, "docs/_build/html")},
    ),
    # The special no-password login endpoint for development
    path(
        "devlogin/",
        login_page,
        {"template_name": "zerver/development/dev_login.html"},
        name="login_page",
    ),
    # Page for testing email templates
    path("emails/", email_page),
    path("emails/generate/", generate_all_emails),
    path("emails/clear/", clear_emails),
    # Listing of useful URLs and various tools for development
    path("devtools/", TemplateView.as_view(template_name="zerver/development/dev_tools.html")),
    # Register new user and realm
    path("devtools/register_user/", register_development_user, name="register_dev_user"),
    path("devtools/register_realm/", register_development_realm, name="register_dev_realm"),
    path(
        "devtools/register_demo_realm/",
        register_demo_development_realm,
        name="register_demo_dev_realm",
    ),
    # Have easy access for error pages
    *(
        path(f"errors/{slug}/", TemplateView.as_view(template_name=template, extra_context=context))
        for _, pages in DEV_ERROR_PAGE_GROUPS
        for slug, template, context in pages
    ),
    path(
        "devtools/error_pages/",
        TemplateView.as_view(
            template_name="zerver/development/error_pages.html",
            extra_context={
                "error_page_groups": [
                    (title, [slug for slug, _, _ in pages])
                    for title, pages in DEV_ERROR_PAGE_GROUPS
                ]
            },
        ),
    ),
    # Add a convenient way to generate webhook messages from fixtures.
    path("devtools/integrations/", dev_panel),
    path(
        "devtools/integrations/check_send_webhook_fixture_message",
        check_send_webhook_fixture_message,
    ),
    path(
        "devtools/integrations/send_all_webhook_fixture_messages", send_all_webhook_fixture_messages
    ),
    path("devtools/integrations/<integration_name>/fixtures", get_fixtures),
    path("config-error/<error_name>", config_error, name="config_error"),
    # Special endpoint to remove all the server-side caches.
    path("flush_caches", remove_caches),
    # Redirect camo URLs for development
    path("external_content/<digest>/<received_url>", handle_camo_url),
    # Endpoints for Showroom components.
    path("devtools/buttons/", showroom_component_buttons),
    path("devtools/banners/", showroom_component_banners),
    path("devtools/inputs/", showroom_component_inputs),
    # Development server for the help center in not run by default, we
    # show this page with zulip.com and view source links instead.
    path("help", help_dev_mode_view),
    path("help/", help_dev_mode_view),
    path("help/<path:subpath>", help_dev_mode_view),
]

v1_api_mobile_patterns = [
    # This is for the signing in through the devAuthBackEnd on mobile apps.
    path("dev_fetch_api_key", api_dev_fetch_api_key),
    # This is for fetching the emails of the admins and the users.
    path("dev_list_users", api_dev_list_users),
]
# Serve static assets via the Django server
if use_prod_static:
    urls += [
        path("static/<path:path>", serve, {"document_root": settings.STATIC_ROOT}),
    ]
else:  # nocoverage

    def serve_static(request: HttpRequest, path: str) -> HttpResponse | FileResponse:
        response = staticfiles_serve(request, path)
        response["Access-Control-Allow-Origin"] = "*"
        return response

    assert settings.STATIC_URL is not None
    urls += static(urlsplit(settings.STATIC_URL).path, view=serve_static)

i18n_urls = [
    path("accounts/login/local/", dev_direct_login, name="login-local"),
    path("confirmation_key/", confirmation_key),
]
urls += i18n_urls
