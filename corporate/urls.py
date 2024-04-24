from typing import Any

from django.conf.urls import include
from django.urls import path
from django.views.generic import RedirectView, TemplateView

from corporate.views.billing_page import (
    billing_page,
    remote_realm_billing_page,
    remote_server_billing_page,
    remote_server_deactivate_page,
    update_plan,
    update_plan_for_remote_realm,
    update_plan_for_remote_server,
)
from corporate.views.event_status import (
    event_status,
    event_status_page,
    remote_realm_event_status,
    remote_realm_event_status_page,
    remote_server_event_status,
    remote_server_event_status_page,
)
from corporate.views.installation_activity import (
    get_installation_activity,
    get_integrations_activity,
)
from corporate.views.portico import (
    app_download_link_redirect,
    apps_view,
    communities_view,
    customer_portal,
    hello_view,
    invoices_page,
    landing_view,
    plans_view,
    remote_realm_customer_portal,
    remote_realm_invoices_page,
    remote_realm_plans_page,
    remote_server_customer_portal,
    remote_server_invoices_page,
    remote_server_plans_page,
    team_view,
)
from corporate.views.realm_activity import get_realm_activity
from corporate.views.remote_activity import get_remote_server_activity
from corporate.views.remote_billing_page import (
    remote_billing_legacy_server_confirm_login,
    remote_billing_legacy_server_from_login_confirmation_link,
    remote_billing_legacy_server_login,
    remote_realm_billing_confirm_email,
    remote_realm_billing_finalize_login,
    remote_realm_billing_from_login_confirmation_link,
)
from corporate.views.session import (
    start_card_update_stripe_session,
    start_card_update_stripe_session_for_realm_upgrade,
    start_card_update_stripe_session_for_remote_realm,
    start_card_update_stripe_session_for_remote_realm_upgrade,
    start_card_update_stripe_session_for_remote_server,
    start_card_update_stripe_session_for_remote_server_upgrade,
)
from corporate.views.sponsorship import (
    remote_realm_sponsorship,
    remote_realm_sponsorship_page,
    remote_server_sponsorship,
    remote_server_sponsorship_page,
    sponsorship,
    sponsorship_page,
)
from corporate.views.support import demo_request, remote_servers_support, support, support_request
from corporate.views.upgrade import (
    remote_realm_upgrade,
    remote_realm_upgrade_page,
    remote_server_upgrade,
    remote_server_upgrade_page,
    upgrade,
    upgrade_page,
)
from corporate.views.user_activity import get_user_activity
from corporate.views.webhook import stripe_webhook
from zerver.lib.rest import rest_path
from zerver.lib.url_redirects import LANDING_PAGE_REDIRECTS

i18n_urlpatterns: Any = [
    # Zephyr/MIT
    path("zephyr/", TemplateView.as_view(template_name="corporate/zephyr.html")),
    path("zephyr-mirror/", TemplateView.as_view(template_name="corporate/zephyr-mirror.html")),
    path("jobs/", TemplateView.as_view(template_name="corporate/jobs.html")),
    # Billing
    path("billing/", billing_page, name="billing_page"),
    path("invoices/", invoices_page, name="invoices_page"),
    path("customer_portal/", customer_portal, name="customer_portal_page"),
    path("sponsorship/", sponsorship_page, name="sponsorship_request"),
    path("upgrade/", upgrade_page, name="upgrade_page"),
    path("support/", support_request),
    path("request-demo/", demo_request),
    path("billing/event_status/", event_status_page, name="event_status_page"),
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),
    # Server admin (user_profile.is_staff) visible stats pages
    path("activity", get_installation_activity),
    path("activity/integrations", get_integrations_activity),
    path("activity/support", support, name="support"),
    path("realm_activity/<realm_str>/", get_realm_activity),
    path("user_activity/<user_profile_id>/", get_user_activity),
    path("activity/remote", get_remote_server_activity),
    path("activity/remote/support", remote_servers_support, name="remote_servers_support"),
]

v1_api_and_json_patterns = [
    rest_path("billing/upgrade", POST=upgrade),
    rest_path("billing/sponsorship", POST=sponsorship),
    rest_path("billing/plan", PATCH=update_plan),
    rest_path("billing/session/start_card_update_session", POST=start_card_update_stripe_session),
    rest_path(
        "upgrade/session/start_card_update_session",
        POST=start_card_update_stripe_session_for_realm_upgrade,
    ),
    rest_path("billing/event/status", GET=event_status),
]

landing_page_urls = [
    # Landing page, features pages, signup form, etc.
    path("hello/", hello_view),
    path("features/", landing_view, {"template_name": "corporate/features.html"}),
    path("plans/", plans_view, name="plans"),
    path("apps/", apps_view),
    path("apps/download/<platform>", app_download_link_redirect),
    path("apps/<platform>", apps_view),
    path(
        "development-community/",
        landing_view,
        {"template_name": "corporate/development-community.html"},
    ),
    path("attribution/", landing_view, {"template_name": "corporate/attribution.html"}),
    path("team/", team_view),
    path("history/", landing_view, {"template_name": "corporate/history.html"}),
    path("values/", landing_view, {"template_name": "corporate/values.html"}),
    path("why-zulip/", landing_view, {"template_name": "corporate/why-zulip.html"}),
    path("self-hosting/", landing_view, {"template_name": "corporate/self-hosting.html"}),
    path("security/", landing_view, {"template_name": "corporate/security.html"}),
    path("try-zulip/", landing_view, {"template_name": "corporate/try-zulip.html"}),
    # /for pages
    path("use-cases/", landing_view, {"template_name": "corporate/for/use-cases.html"}),
    path(
        "for/communities/",
        landing_view,
        {"template_name": "corporate/for/communities.html"},
    ),
    path("for/education/", landing_view, {"template_name": "corporate/for/education.html"}),
    path("for/events/", landing_view, {"template_name": "corporate/for/events.html"}),
    path("for/open-source/", landing_view, {"template_name": "corporate/for/open-source.html"}),
    path("for/research/", landing_view, {"template_name": "corporate/for/research.html"}),
    path("for/business/", landing_view, {"template_name": "corporate/for/business.html"}),
    # case-studies
    path(
        "case-studies/idrift/",
        landing_view,
        {"template_name": "corporate/case-studies/idrift-case-study.html"},
    ),
    path(
        "case-studies/gut-contact/",
        landing_view,
        {"template_name": "corporate/case-studies/gut-contact-case-study.html"},
    ),
    path(
        "case-studies/end-point/",
        landing_view,
        {"template_name": "corporate/case-studies/end-point-case-study.html"},
    ),
    path(
        "case-studies/atolio/",
        landing_view,
        {"template_name": "corporate/case-studies/atolio-case-study.html"},
    ),
    path(
        "case-studies/semsee/",
        landing_view,
        {"template_name": "corporate/case-studies/semsee-case-study.html"},
    ),
    path(
        "case-studies/tum/",
        landing_view,
        {"template_name": "corporate/case-studies/tum-case-study.html"},
    ),
    path(
        "case-studies/ucsd/",
        landing_view,
        {"template_name": "corporate/case-studies/ucsd-case-study.html"},
    ),
    path(
        "case-studies/rust/",
        landing_view,
        {"template_name": "corporate/case-studies/rust-case-study.html"},
    ),
    path(
        "case-studies/lean/",
        landing_view,
        {"template_name": "corporate/case-studies/lean-case-study.html"},
    ),
    path(
        "case-studies/asciidoctor/",
        landing_view,
        {"template_name": "corporate/case-studies/asciidoctor-case-study.html"},
    ),
    path(
        "case-studies/recurse-center/",
        landing_view,
        {"template_name": "corporate/case-studies/recurse-center-case-study.html"},
    ),
    path("communities/", communities_view),
]

# Redirects due to us having moved or combined landing pages:
for redirect in LANDING_PAGE_REDIRECTS:
    old_url = redirect.old_url.lstrip("/")
    landing_page_urls += [path(old_url, RedirectView.as_view(url=redirect.new_url, permanent=True))]

i18n_urlpatterns += landing_page_urls

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    path("remote-billing-login/<signed_billing_access_token>", remote_realm_billing_finalize_login),
    path(
        "remote-billing-login/<signed_billing_access_token>/confirm/",
        remote_realm_billing_confirm_email,
    ),
    path(
        "remote-billing-login/do_confirm/<confirmation_key>",
        remote_realm_billing_from_login_confirmation_link,
        name="remote_realm_billing_from_login_confirmation_link",
    ),
    # Remote server billing endpoints.
    path("realm/<realm_uuid>/plans/", remote_realm_plans_page, name="remote_realm_plans_page"),
    path(
        "server/<server_uuid>/plans/",
        remote_server_plans_page,
        name="remote_server_plans_page",
    ),
    path(
        "realm/<realm_uuid>/billing/", remote_realm_billing_page, name="remote_realm_billing_page"
    ),
    path(
        "server/<server_uuid>/billing/",
        remote_server_billing_page,
        name="remote_server_billing_page",
    ),
    path(
        "realm/<realm_uuid>/upgrade/", remote_realm_upgrade_page, name="remote_realm_upgrade_page"
    ),
    path(
        "server/<server_uuid>/upgrade/",
        remote_server_upgrade_page,
        name="remote_server_upgrade_page",
    ),
    path(
        "realm/<realm_uuid>/sponsorship/",
        remote_realm_sponsorship_page,
        name="remote_realm_sponsorship_page",
    ),
    path(
        "server/<server_uuid>/sponsorship/",
        remote_server_sponsorship_page,
        name="remote_server_sponsorship_page",
    ),
    path(
        "server/<server_uuid>/deactivate/",
        remote_server_deactivate_page,
        name="remote_server_deactivate_page",
    ),
    path(
        "serverlogin/",
        remote_billing_legacy_server_login,
        name="remote_billing_legacy_server_login",
    ),
    path(
        "serverlogin/<server_uuid>/confirm/",
        remote_billing_legacy_server_confirm_login,
        name="remote_billing_legacy_server_confirm_login",
    ),
    path(
        "serverlogin/do_confirm/<confirmation_key>",
        remote_billing_legacy_server_from_login_confirmation_link,
        name="remote_billing_legacy_server_from_login_confirmation_link",
    ),
    path(
        "realm/<realm_uuid>/billing/event_status/",
        remote_realm_event_status_page,
        name="remote_realm_event_status_page",
    ),
    path(
        "server/<server_uuid>/billing/event_status/",
        remote_server_event_status_page,
        name="remote_server_event_status_page",
    ),
    path(
        "realm/<realm_uuid>/invoices/",
        remote_realm_invoices_page,
        name="remote_realm_invoices_page",
    ),
    path(
        "server/<server_uuid>/invoices/",
        remote_server_invoices_page,
        name="remote_server_invoices_page",
    ),
    path(
        "realm/<realm_uuid>/customer_portal/",
        remote_realm_customer_portal,
        name="remote_realm_customer_portal_page",
    ),
    path(
        "server/<server_uuid>/customer_portal/",
        remote_server_customer_portal,
        name="remote_server_customer_portal_page",
    ),
    # Remote variants of above API endpoints.
    path("json/realm/<realm_uuid>/billing/sponsorship", remote_realm_sponsorship),
    path("json/server/<server_uuid>/billing/sponsorship", remote_server_sponsorship),
    path(
        "json/realm/<realm_uuid>/billing/session/start_card_update_session",
        start_card_update_stripe_session_for_remote_realm,
    ),
    path(
        "json/server/<server_uuid>/billing/session/start_card_update_session",
        start_card_update_stripe_session_for_remote_server,
    ),
    path(
        "json/realm/<realm_uuid>/upgrade/session/start_card_update_session",
        start_card_update_stripe_session_for_remote_realm_upgrade,
    ),
    path(
        "json/server/<server_uuid>/upgrade/session/start_card_update_session",
        start_card_update_stripe_session_for_remote_server_upgrade,
    ),
    path("json/realm/<realm_uuid>/billing/event/status", remote_realm_event_status),
    path("json/server/<server_uuid>/billing/event/status", remote_server_event_status),
    path("json/realm/<realm_uuid>/billing/upgrade", remote_realm_upgrade),
    path("json/server/<server_uuid>/billing/upgrade", remote_server_upgrade),
    path("json/realm/<realm_uuid>/billing/plan", update_plan_for_remote_realm),
    path("json/server/<server_uuid>/billing/plan", update_plan_for_remote_server),
]

urlpatterns += [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]
